variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "region_name" {
  description = "Logical region name (e.g. region-a)"
  type        = string
  default     = "region-a"
}
