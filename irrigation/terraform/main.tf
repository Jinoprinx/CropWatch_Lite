# CropWatch Lite - Smart Irrigation AWS Infrastructure
# Terraform v1.6+ | Provider: aws ~> 5.0
# Provisions: AWS IoT Core (8 ESP32 things), Lambda fusion engine,
#             DynamoDB telemetry table, IoT Topic Rules

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
}

# -------------------------------------------------------
# IoT Things (one per ESP32 node)
# -------------------------------------------------------
resource "aws_iot_thing" "sensor_nodes" {
  count = var.num_sensor_nodes
  name  = "${var.field_id}-node-${count.index + 1}"
  attributes = {
    field_id = var.field_id
    zone_id  = element(var.zone_ids, floor(count.index / 2))
  }
}

# IoT Policy: allow nodes to publish telemetry and receive commands
resource "aws_iot_policy" "node_policy" {
  name = "${var.project_name}-node-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["iot:Connect"]
        Resource = "arn:aws:iot:${var.aws_region}:*:client/${var.field_id}-*"
      },
      {
        Effect   = "Allow"
        Action   = ["iot:Publish"]
        Resource = "arn:aws:iot:${var.aws_region}:*:topic/cropwatch/telemetry/*"
      },
      {
        Effect   = "Allow"
        Action   = ["iot:Subscribe", "iot:Receive"]
        Resource = "arn:aws:iot:${var.aws_region}:*:topic/cropwatch/commands/*"
      }
    ]
  })
}

# -------------------------------------------------------
# DynamoDB - Telemetry History Table
# -------------------------------------------------------
resource "aws_dynamodb_table" "telemetry" {
  name         = "${var.project_name}-telemetry"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "node_id"
  range_key    = "timestamp_utc"

  attribute {
    name = "node_id"
    type = "S"
  }
  attribute {
    name = "timestamp_utc"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }

  tags = { Project = var.project_name, Environment = var.environment }
}

resource "aws_dynamodb_table" "irrigation_log" {
  name         = "${var.project_name}-irrigation-log"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "field_id"
  range_key    = "timestamp_utc"

  attribute {
    name = "field_id"
    type = "S"
  }
  attribute {
    name = "timestamp_utc"
    type = "S"
  }

  tags = { Project = var.project_name, Environment = var.environment }
}

# -------------------------------------------------------
# Lambda - Fusion Engine
# -------------------------------------------------------
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"]
      Resource = [aws_dynamodb_table.telemetry.arn, aws_dynamodb_table.irrigation_log.arn]
    }, {
      Effect   = "Allow"
      Action   = ["iot:Publish"]
      Resource = "arn:aws:iot:${var.aws_region}:*:topic/cropwatch/commands/*"
    }]
  })
}

resource "aws_lambda_function" "fusion_engine" {
  function_name = "${var.project_name}-fusion-engine"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:${var.image_tag}"
  timeout       = 60
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TELEMETRY_TABLE = aws_dynamodb_table.telemetry.name
      DYNAMODB_LOG_TABLE       = aws_dynamodb_table.irrigation_log.name
      AWS_REGION_NAME          = var.aws_region
      IOT_ENDPOINT             = var.iot_endpoint
    }
  }

  tags = { Project = var.project_name }
}

# -------------------------------------------------------
# IoT Topic Rules: MQTT → Lambda → DynamoDB
# -------------------------------------------------------
resource "aws_iam_role" "iot_rule_role" {
  name = "${var.project_name}-iot-rule-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "iot.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "iot_lambda_invoke" {
  role = aws_iam_role.iot_rule_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.fusion_engine.arn
    }]
  })
}

resource "aws_iot_topic_rule" "telemetry_to_lambda" {
  name        = "${replace(var.project_name, "-", "_")}_telemetry_rule"
  enabled     = true
  sql         = "SELECT * FROM 'cropwatch/telemetry/+'"
  sql_version = "2016-03-23"

  lambda {
    function_arn = aws_lambda_function.fusion_engine.arn
  }
}

resource "aws_lambda_permission" "iot_invoke" {
  statement_id  = "AllowIoTCoreInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fusion_engine.function_name
  principal     = "iot.amazonaws.com"
  source_arn    = aws_iot_topic_rule.telemetry_to_lambda.arn
}
