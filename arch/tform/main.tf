data "scaleway_instance_security_group" "pangolin" {
  name = var.security_group_name
  zone = var.zone
}

data "scaleway_instance_server" "pangolin" {
  server_id = var.instance_id
  zone      = var.zone
}

locals {
  # The CS2 server's own ports (from docker-compose.yml): game traffic on 27015/tcp+udp,
  # SourceTV/relay on 27020/udp. Only present in the rule list while the server is running.
  
  cs2_inbound_rules = var.cs2_server_running ? [
    { protocol = "TCP", port = 27015, ip_range = "0.0.0.0/0" },
    { protocol = "UDP", port = 27015, ip_range = "0.0.0.0/0" },
    { protocol = "UDP", port = 27020, ip_range = "0.0.0.0/0" },
  ] : []

  # IMPORTANT: this resource takes exclusive ownership of the security group's entire rule
  # list - whatever isn't declared here is removed on apply. Before the first `terraform
  # apply`, fill this in with every inbound rule the group currently has (Pangolin's own
  # dashboard/tunnel ports etc.) so they aren't wiped out. Get the current list from the
  # Scaleway console (Instances > Security Groups > home-lab-pangolin > Rules) or:
  #   scw instance security-group-rule list security-group-id=<id> zone=<zone>
  
  existing_inbound_rules = [
    { protocol = "TCP", port = 80,    ip_range = "0.0.0.0/0" },
    { protocol = "TCP", port = 443,   ip_range = "0.0.0.0/0" },
    { protocol = "TCP", port = 22,    ip_range = "0.0.0.0/0" },
    { protocol = "UDP", port = 51820, ip_range = "0.0.0.0/0" },
  ]

  existing_outbound_rules = [
  ]

  inbound_rules = concat(local.existing_inbound_rules, local.cs2_inbound_rules)
}

resource "scaleway_instance_security_group_rules" "pangolin" {
  security_group_id = data.scaleway_instance_security_group.pangolin.id

  dynamic "inbound_rule" {
    for_each = local.inbound_rules
    content {
      action   = "accept"
      protocol = inbound_rule.value.protocol
      port     = inbound_rule.value.port
      ip_range = try(inbound_rule.value.ip_range, "0.0.0.0/0")
    }
  }

  dynamic "outbound_rule" {
    for_each = local.existing_outbound_rules
    content {
      action   = "accept"
      protocol = outbound_rule.value.protocol
      port     = try(outbound_rule.value.port, null)
      ip_range = try(outbound_rule.value.ip_range, "0.0.0.0/0")
    }
  }
}
