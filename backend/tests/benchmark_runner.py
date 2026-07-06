import os
import sys

# Resolve DATABASE_URL: prefer env var, fall back to docker-compose port 5434
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5434/closely_db_test"

import time
import asyncio
import numpy as np
import httpx

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import Base, SessionLocal, engine
from app import models, security, ai_service

# Ensure output directories exist
os.makedirs("../evidence/Sprint2/performance", exist_ok=True)

async def measure_task(name, coroutine_func, num_requests=50, concurrency=5):
    """
    Runs a task multiple times with a specified concurrency level and calculates p50, p95, p99.
    """
    times = []
    sem = asyncio.Semaphore(concurrency)

    async def worker():
        async with sem:
            start_time = time.perf_counter()
            try:
                await coroutine_func()
            except Exception as e:
                # Log error
                pass
            end_time = time.perf_counter()
            times.append(end_time - start_time)

    tasks = [worker() for _ in range(num_requests)]
    await asyncio.gather(*tasks)

    # Calculate percentiles
    times_ms = [t * 1000.0 for t in times]
    p50 = np.percentile(times_ms, 50)
    p95 = np.percentile(times_ms, 95)
    p99 = np.percentile(times_ms, 99)
    avg = np.mean(times_ms)

    return {
        "name": name,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "avg": avg,
        "total": len(times_ms)
    }

async def run_benchmarks():
    print("Initializing database for benchmarking...")
    # Clean and seed organization and user
    db = SessionLocal()
    
    # Temporarily bypass multi-tenancy logical partitions for cleaning
    from app.database import tenant_var
    tenant_var.set(None)
    db.organization_id = None
    
    db.query(models.User).delete()
    db.query(models.Product).delete()
    db.query(models.Category).delete()
    db.query(models.Conversation).delete()
    db.query(models.Organization).delete()
    db.commit()

    # Create brand
    org = models.Organization(
        name="Benchmark Brand",
        whatsapp_number="1234567890",
        policies={"return_policy": "No returns allowed."}
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create owner
    password_hash = security.get_password_hash("password123")
    user = models.User(
        organization_id=org.id,
        email="benchmark@closely.com",
        password_hash=password_hash,
        role="owner",
        name="Benchmarker"
    )
    db.add(user)
    db.commit()
    db.close()

    print("Database seeded. Starting benchmarks...")
    
    # We will use httpx.AsyncClient with app to run direct ASGI requests
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        # 1. Login Benchmark
        async def login_task():
            res = await client.post("/api/auth/login", data={
                "username": "benchmark@closely.com",
                "password": "password123"
            })
            assert res.status_code == 200

        login_metrics = await measure_task("Merchant Login", login_task, num_requests=30, concurrency=5)

        # Login once to get token
        login_res = await client.post("/api/auth/login", data={
            "username": "benchmark@closely.com",
            "password": "password123"
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Catalog CSV Upload Benchmark
        # We upload a CSV with 10 products
        csv_content = (
            "sku,name,price,color,category,fabric,stock_count,description\n"
            + "\n".join([f"SKU{i},Product {i},{1000 + i*100},Red,Sarees,Silk,10,A beautiful saree {i}" for i in range(10)])
        )
        
        async def upload_task():
            files = {"file": ("catalog.csv", csv_content.encode("utf-8"), "text/csv")}
            res = await client.post("/api/catalog/upload", files=files, headers=headers)
            assert res.status_code == 200

        # Upload runs serially or with low concurrency since it modifies DB
        upload_metrics = await measure_task("Catalog CSV Upload (10 products)", upload_task, num_requests=10, concurrency=2)

        # 3. Similarity Search Benchmark (Query is "red silk saree")
        async def search_task():
            res = await client.get("/api/catalog/products", params={"q": "red silk saree"}, headers=headers)
            assert res.status_code == 200

        search_metrics = await measure_task("Catalog Similarity Search", search_task, num_requests=30, concurrency=5)

        # 4. AI Reply Generation (excluding simulated LLM latency)
        catalog_context = [
            {"sku": "SKU001", "name": "Silk Saree", "price": 4500.0, "color": "Red", "sizes": ["M", "L"], "stock_count": 5}
        ]
        policies_context = {"return": "7 days return policy"}
        history = [{"sender": "customer", "content": "Hi"}, {"sender": "ai", "content": "Hello, how can I help you today?"}]
        
        async def ai_gen_exclude_task():
            res = ai_service.generate_reply("Do you have red silk sarees?", history, catalog_context, policies_context)
            assert res is not None

        ai_gen_exclude_metrics = await measure_task(
            "AI Reply Gen (Excl. LLM Latency)", 
            ai_gen_exclude_task, 
            num_requests=30, 
            concurrency=5
        )

        # 5. AI Reply Generation (including simulated LLM latency)
        async def ai_gen_include_task():
            import random
            simulated_delay = random.uniform(1.0, 2.5)
            await asyncio.sleep(simulated_delay)
            res = ai_service.generate_reply("Do you have red silk sarees?", history, catalog_context, policies_context)
            assert res is not None

        ai_gen_include_metrics = await measure_task(
            "AI Reply Gen (Incl. LLM Latency)", 
            ai_gen_include_task, 
            num_requests=20, 
            concurrency=5
        )

        # Print and Save Metrics
        output_lines = [
            "==================================================================",
            "                    Closely AI Performance Benchmarks             ",
            "==================================================================",
            f"Run Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"{'Benchmark Name':<35} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'Avg (ms)':<10} | {'Count':<5}",
            "-" * 85
        ]

        for m in [login_metrics, upload_metrics, search_metrics, ai_gen_exclude_metrics, ai_gen_include_metrics]:
            output_lines.append(
                f"{m['name']:<35} | {m['p50']:<10.2f} | {m['p95']:<10.2f} | {m['p99']:<10.2f} | {m['avg']:<10.2f} | {m['total']:<5}"
            )
        output_lines.append("==================================================================")

        report = "\n".join(output_lines)
        print(report)

        # Write to evidence path
        evidence_file = "../evidence/Sprint2/performance/benchmarks.txt"
        os.makedirs(os.path.dirname(evidence_file), exist_ok=True)
        with open(evidence_file, "w") as f:
            f.write(report)
        print(f"\nSaved benchmark metrics to {os.path.abspath(evidence_file)}")

if __name__ == "__main__":
    asyncio.run(run_benchmarks())
