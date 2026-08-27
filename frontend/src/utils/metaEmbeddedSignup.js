/**
 * Meta Embedded Signup SDK Integration Helper
 * Provides hardened, origin-validated popup handling and OAuth code exchange.
 */

let sdkPromise = null;

export function loadMetaSdk(appId, apiVersion = 'v20.0') {
  if (window.FB) {
    return Promise.resolve(window.FB);
  }
  if (sdkPromise) {
    return sdkPromise;
  }

  sdkPromise = new Promise((resolve, reject) => {
    window.fbAsyncInit = function () {
      window.FB.init({
        appId: appId || 'mock_app_id',
        autoLogAppEvents: true,
        xfbml: true,
        version: apiVersion
      });
      resolve(window.FB);
    };

    const script = document.createElement('script');
    script.id = 'facebook-jssdk';
    script.src = 'https://connect.facebook.net/en_US/sdk.js';
    script.async = true;
    script.defer = true;
    script.onerror = () => reject(new Error('Failed to load Meta JavaScript SDK'));
    document.body.appendChild(script);
  });

  return sdkPromise;
}

export async function launchEmbeddedSignup({ apiFetch, onStatusChange }) {
  // 1. Fetch config and single-use session nonce from backend
  const configRes = await apiFetch('/api/brand/whatsapp/embedded-signup-config');
  if (!configRes.ok) {
    throw new Error('Failed to retrieve Meta Embedded Signup configuration.');
  }
  const { app_id, config_id, api_version, session_nonce } = await configRes.json();

  if (onStatusChange) onStatusChange('Initializing Meta Embedded Signup...');

  // 2. Load SDK
  await loadMetaSdk(app_id, api_version);

  // 3. Attach hardened postMessage listener for WA_EMBEDDED_SIGNUP events
  let wabaIdHint = null;
  let phoneNumberIdHint = null;

  const messageHandler = (event) => {
    // Strict Origin Verification
    if (event.origin !== 'https://www.facebook.com' && event.origin !== 'https://web.facebook.com') {
      return;
    }

    try {
      const payload = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
      if (payload && payload.type === 'WA_EMBEDDED_SIGNUP') {
        if (payload.data) {
          wabaIdHint = payload.data.waba_id || wabaIdHint;
          phoneNumberIdHint = payload.data.phone_number_id || phoneNumberIdHint;
          if (payload.data.event === 'FINISH' && onStatusChange) {
            onStatusChange('Meta signup complete. Finalizing connection...');
          }
        }
      }
    } catch {
      // Ignore unparseable non-Meta messages
    }
  };

  window.addEventListener('message', messageHandler);

  // 4. Launch FB.login popup
  return new Promise((resolve, reject) => {
    window.FB.login(
      async (response) => {
        window.removeEventListener('message', messageHandler);

        if (!response || !response.authResponse || !response.authResponse.code) {
          return reject(new Error('Embedded Signup was cancelled or closed without authorization.'));
        }

        const authCode = response.authResponse.code;
        if (onStatusChange) onStatusChange('Exchanging authorization code securely...');

        try {
          // 5. Submit authorization code and one-time session nonce to backend
          const callbackRes = await apiFetch('/api/brand/whatsapp/embedded-signup-callback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              code: authCode,
              session_nonce: session_nonce,
              waba_id_hint: wabaIdHint,
              phone_number_id_hint: phoneNumberIdHint
            })
          });

          const result = await callbackRes.json();
          if (!callbackRes.ok) {
            return reject(new Error(result.detail || result.message || 'Meta authorization code exchange failed.'));
          }

          resolve(result);
        } catch (err) {
          reject(err);
        }
      },
      {
        config_id: config_id,
        response_type: 'code',
        override_default_response_type: true,
        extras: {
          setup: {},
          featureType: '',
          sessionInfoVersion: '3'
        }
      }
    );
  });
}
