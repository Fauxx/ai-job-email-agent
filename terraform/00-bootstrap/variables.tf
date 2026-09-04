variable "github_token" {
  description = "GitHub Personal Access Token (PAT) with repo scope"
  type        = string
  sensitive   = true
}

variable "github_repository" {
  description = "Name of the GitHub repository"
  type        = string
  default     = "ai-job-email-agent"
}

variable "imap_user" {
  type      = string
  sensitive = true
}

variable "imap_pass" {
  type      = string
  sensitive = true
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
}

variable "telegram_bot_token" {
  type      = string
  sensitive = true
}

variable "telegram_chat_id" {
  type      = string
  sensitive = true
}
