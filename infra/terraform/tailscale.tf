# Tailscale subnet router: a tiny EC2 instance that bridges your laptop
# (via Tailscale) into the VPC where RDS lives. RDS itself never gets a
# public endpoint.

# Latest Amazon Linux 2023 ARM64 AMI (matches t4g.* ARM instance family).
data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# IAM role for the router. Currently grants only SSM Session Manager so we
# can shell into the box from the AWS console as an emergency channel
# (Tailscale SSH is the primary path).
resource "aws_iam_role" "tailscale_router" {
  name = "${local.name_prefix}-tailscale-router"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "tailscale_router_ssm" {
  role       = aws_iam_role.tailscale_router.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "tailscale_router" {
  name = "${local.name_prefix}-tailscale-router"
  role = aws_iam_role.tailscale_router.name
}

# The router instance itself.
resource "aws_instance" "tailscale_router" {
  ami           = data.aws_ssm_parameter.al2023_arm64.value
  instance_type = var.tailscale_router_instance_type

  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.tailscale_router.id]
  iam_instance_profile   = aws_iam_instance_profile.tailscale_router.name

  user_data = templatefile("${path.module}/templates/tailscale_router_userdata.sh.tftpl", {
    tailscale_auth_key = var.tailscale_auth_key
    advertise_routes   = data.aws_vpc.default.cidr_block
    hostname           = "${local.name_prefix}-router"
  })

  # If we change user_data later (e.g., to upgrade Tailscale or rotate the
  # auth key), the instance must be replaced — re-running tailscale up on a
  # live host doesn't re-pick-up new flags.
  user_data_replace_on_change = true

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "${local.name_prefix}-tailscale-router"
    Role = "tailscale-subnet-router"
  }
}
