variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "db_username" {
  description = "PostgreSQL administrator username"
  type        = string
  default     = "closely_admin"
}

variable "db_password" {
  description = "PostgreSQL administrator password"
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API Key"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "HMAC secret for signing JWT auth tokens"
  type        = string
  sensitive   = true
}
