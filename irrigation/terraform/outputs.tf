output "iot_thing_names"        { value = aws_iot_thing.sensor_nodes[*].name }
output "lambda_function_name"   { value = aws_lambda_function.fusion_engine.function_name }
output "telemetry_table_name"   { value = aws_dynamodb_table.telemetry.name }
output "irrigation_log_table"   { value = aws_dynamodb_table.irrigation_log.name }
