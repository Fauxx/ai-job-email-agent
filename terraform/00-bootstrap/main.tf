data "github_repository" "agent" {
  name = var.github_repository
}

resource "github_actions_secret" "imap_user" {
  repository       = data.github_repository.agent.name
  secret_name      = "IMAP_USER"
  plaintext_value  = var.imap_user
}

resource "github_actions_secret" "imap_pass" {
  repository       = data.github_repository.agent.name
  secret_name      = "IMAP_PASS"
  plaintext_value  = var.imap_pass
}

resource "github_actions_secret" "gemini_api_key" {
  repository       = data.github_repository.agent.name
  secret_name      = "GEMINI_API_KEY"
  plaintext_value  = var.gemini_api_key
}

resource "github_actions_secret" "telegram_bot_token" {
  repository       = data.github_repository.agent.name
  secret_name      = "TELEGRAM_BOT_TOKEN"
  plaintext_value  = var.telegram_bot_token
}

resource "github_actions_secret" "telegram_chat_id" {
  repository       = data.github_repository.agent.name
  secret_name      = "TELEGRAM_CHAT_ID"
  plaintext_value  = var.telegram_chat_id
}
