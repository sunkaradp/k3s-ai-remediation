variable "hcloud_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "name" {
  description = "Prefix for all resources"
  type        = string
  default     = "k3s-remediation"
}

variable "server_type" {
  description = "cx32 = 4 vCPU / 8 GB, enough for monitoring + a small LLM"
  type        = string
  default     = "cx32"
}

variable "location" {
  type    = string
  default = "nbg1"
}

variable "k3s_version" {
  type    = string
  default = "v1.31.4+k3s1"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "admin_cidrs" {
  description = "IPs allowed to reach SSH and the k8s API, e.g. [\"203.0.113.10/32\"]"
  type        = list(string)
}
