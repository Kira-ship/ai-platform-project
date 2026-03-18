provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

# 创建 ECR 仓库
resource "aws_ecr_repository" "backend_repo" {
  name                 = "my-dachuang-backend"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
}

# 生命周期策略：只保留最近 10 个镜像 (申报书亮点)
resource "aws_ecr_lifecycle_policy" "backend_policy" {
  repository = aws_ecr_repository.backend_repo.name
  policy     = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus     = "any"
        countType     = "imageCountMoreThan"
        countNumber   = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

output "ecr_url" {
  value = aws_ecr_repository.backend_repo.repository_url
}
