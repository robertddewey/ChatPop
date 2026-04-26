# Use the account's default VPC. Avoids the cost and complexity of building
# a new VPC; the default VPC has subnets in every AZ in the region.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# RDS requires a subnet group spanning at least 2 AZs (even for single-AZ
# deployments) so it has somewhere to fail over if you ever enable Multi-AZ.
resource "aws_db_subnet_group" "dev" {
  name       = "${local.name_prefix}-rds"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name = "${local.name_prefix}-rds-subnet-group"
  }
}

# --- Security groups ------------------------------------------------------

# Tailscale router: outbound only. No public SSH inbound — administrative
# access is via Tailscale SSH (--ssh flag in user data), authenticated
# through the tailnet.
resource "aws_security_group" "tailscale_router" {
  name        = "${local.name_prefix}-tailscale-router"
  description = "ChatPop dev - Tailscale subnet router. Outbound only."
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "All outbound (Tailscale needs UDP 41641 + DERP fallbacks; package install needs HTTPS)."
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-tailscale-router"
  }
}

# RDS: inbound from the Tailscale router SG only. No public access.
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds"
  description = "ChatPop dev - RDS. Inbound from Tailscale router SG only."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Postgres from Tailscale router"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.tailscale_router.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-rds"
  }
}
