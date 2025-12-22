-- Lab 04: Model Serving Checker
-- Tests FastAPI + Redis model serving implementation
-- Demonstrates http_batch and http_batch_repeat check types

lab = {
    id = "04",
    name = "Model Serving",
    env_prefix = "NPL",
}

required_env = {
    { name = "STUDENT", error = "Student ID required (e.g., ivan.ivanov)" },
    { name = "TOKEN", error = "Authentication token required" },
    { name = "API_URL", error = "API URL required (e.g., http://localhost:8000)" },
    { name = "MINERVA", error = "Analytics endpoint required" },
}

usage_text = [[
Lab 04 Checker - Model Serving

This checker validates your FastAPI + Redis model serving implementation.

Required environment variables:
  {{.EnvPrefix}}_STUDENT  - Your student ID (e.g., ivan.ivanov)
  {{.EnvPrefix}}_TOKEN    - Your authentication token
  {{.EnvPrefix}}_API_URL  - Your API base URL (e.g., http://localhost:8000)
  {{.EnvPrefix}}_MINERVA  - Analytics endpoint

Example:
  docker run --rm -it --env-file env.conf {{.Image}}
]]

confirm_display = {
    "STUDENT",
    { name = "TOKEN", masked = true },
    "API_URL",
}

analytics = {
    skip_tls = true,
    common_data = {
        student = "STUDENT",
    },
    headers = {
        ["x-npl-lab"] = "04",
        ["x-npl-student"] = "env:STUDENT",
        ["Authorization"] = "Bearer env:TOKEN",
    },
}

-- Embed the test data file
embedded_data = {
    { name = "predictions", file = "testdata/lab04_predictions.json" },
}

checks = {
    -- Step 1: Health check
    {
        type = "http_request",
        name = "health_check",
        method = "GET",
        url = "{{.API_URL}}/health",
        expected_status = 200,
        message_before = "Checking API health...",
        message_success = "API is healthy",
        response_check = {
            json_field = "status",
            expected = "healthy",
        },
        on_failure = {
            event = "010_health_failed",
            message = "Health check failed - is your API running?",
        },
        on_success = { event = "011_health_passed" },
    },

    -- Step 2: Model info check
    {
        type = "http_request",
        name = "model_info",
        method = "GET",
        url = "{{.API_URL}}/model/info",
        expected_status = 200,
        message_before = "Checking model info...",
        message_success = "Model info validated",
        response_check = {
            json_field = "n_features",
            expected = "8",
        },
        on_failure = {
            event = "020_model_info_failed",
            message = "Model info check failed",
        },
        on_success = { event = "021_model_info_passed" },
    },

    -- Step 3: Batch predictions
    {
        type = "http_batch",
        name = "predictions",
        method = "POST",
        url = "{{.API_URL}}/predict",
        content_type = "application/json",
        expected_status = 200,
        test_data = "predictions",
        request_template = '{"user_id": "${user_id}", "post_id": "${post_id}"}',
        message_before = "Running prediction tests...",
        message_success = "All predictions correct",
        delay_ms = 10,
        response_checks = {
            { field = "prediction", from_data = "expected" },
            { field = "cached", expected = "false" },
        },
        on_failure = {
            event = "030_predictions_failed",
            message = "Prediction validation failed",
        },
        on_success = { event = "031_predictions_passed" },
    },

    -- Step 4: Cache validation (repeat same requests)
    {
        type = "http_batch_repeat",
        name = "cache_check",
        method = "POST",
        url = "{{.API_URL}}/predict",
        content_type = "application/json",
        expected_status = 200,
        reuse = "predictions",
        message_before = "Validating cache behavior...",
        message_success = "Cache working correctly",
        delay_ms = 10,
        response_checks = {
            { field = "cached", expected = "true" },
        },
        on_failure = {
            event = "040_cache_failed",
            message = "Cache validation failed - cached should be true on repeat",
        },
        on_success = { event = "041_cache_passed" },
    },

    -- Step 5: Stats endpoint check
    {
        type = "http_request",
        name = "stats_check",
        method = "GET",
        url = "{{.API_URL}}/stats",
        expected_status = 200,
        message_before = "Checking stats endpoint...",
        message_success = "Stats endpoint working",
        on_failure = {
            event = "050_stats_failed",
            message = "Stats endpoint check failed",
        },
        on_success = { event = "051_stats_passed" },
    },
}

success_message = "Lab 04 completed successfully! Your model serving implementation is correct."
