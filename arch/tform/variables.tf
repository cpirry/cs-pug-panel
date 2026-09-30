variable "zone" {
  description = "Scaleway zone the pangolin instance and its security group live in"
  type        = string
  default     = "nl-ams-1"
}

variable "security_group_name" {
  description = "Name of the existing Scaleway security group to manage the CS2 ports on"
  type        = string
  default     = "home-lab-pangolin"
}

variable "instance_id" {
  description = "ID of the existing pangolin instance"
  type        = string
  default     = "663b9829-74aa-4b99-846f-cbf2dfde75ea"
}

variable "cs2_server_running" {
  description = "Whether the CS2 dedicated server is currently running. Toggle this and re-apply to open/close its ports on the security group."
  type        = bool
  default     = false
}
