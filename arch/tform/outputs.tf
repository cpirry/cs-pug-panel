output "security_group_id" {
  description = "ID of the managed security group"
  value       = data.scaleway_instance_security_group.pangolin.id
}

output "instance_public_ip" {
  description = "Primary public IP of the pangolin instance, if any"
  value       = try(data.scaleway_instance_server.pangolin.public_ips[0].address, null)
}

output "cs2_ports_open" {
  description = "Whether the CS2 server's ports are currently open on the security group"
  value       = var.cs2_server_running
}
