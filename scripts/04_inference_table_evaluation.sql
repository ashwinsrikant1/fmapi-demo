-- ============================================================================
-- Scene 3 & 4b: Inference Table Queries for Demo
-- ============================================================================
-- Run these in a Databricks SQL editor or notebook.
-- Replace {catalog} and {schema} with your config values (default: main.fmapi_demo).
-- Inference tables take up to 1 hour to populate after requests are sent.


-- ============================================================================
-- QUERY 1: Raw Inference Table Data
-- Shows the actual request/response payloads logged by AI Gateway.
-- Demo point: "Every request is automatically logged — no code changes needed."
-- ============================================================================

SELECT
    request_time,
    source.endpoint_name,
    request,
    response,
    input_token_count,
    output_token_count,
    request_metadata
FROM {catalog}.{schema}.`demo-claude-opus-4-6_payload`
ORDER BY request_time DESC
LIMIT 20;


-- ============================================================================
-- QUERY 2: Model Evaluation — JOIN inference outputs with ground truth
-- This is Scene 4b's key moment: data proximity enables eval without moving data.
-- Demo point: "Your inference outputs live in the same lakehouse as your eval data."
-- ============================================================================

SELECT
    gt.prompt,
    gt.expected_response,
    gt.quality_score AS expected_quality,
    gt.category,
    inf.response AS actual_response,
    inf.input_token_count,
    inf.output_token_count,
    inf.request_time
FROM {catalog}.{schema}.evaluation_ground_truth gt
LEFT JOIN (
    SELECT
        request:messages[0].content AS prompt_text,
        response:choices[0].message.content AS response,
        input_token_count,
        output_token_count,
        request_time,
        ROW_NUMBER() OVER (PARTITION BY request:messages[0].content ORDER BY request_time DESC) AS rn
    FROM {catalog}.{schema}.`demo-claude-opus-4-6_payload`
) inf
    ON gt.prompt = inf.prompt_text AND inf.rn = 1
ORDER BY gt.category;


-- ============================================================================
-- QUERY 3: Cross-Model Response Comparison
-- Compare how different models answered the same prompts.
-- Demo point: "Same prompt, three providers, all in one query."
-- ============================================================================

SELECT
    source.endpoint_name AS endpoint,
    request:messages[0].content AS prompt,
    response:choices[0].message.content AS model_response,
    input_token_count,
    output_token_count,
    request_time
FROM {catalog}.{schema}.`demo-claude-opus-4-6_payload`
WHERE request:messages[0].content IS NOT NULL

UNION ALL

SELECT
    source.endpoint_name AS endpoint,
    request:messages[0].content AS prompt,
    response:choices[0].message.content AS model_response,
    input_token_count,
    output_token_count,
    request_time
FROM {catalog}.{schema}.`demo-gpt-5-2_payload`
WHERE request:messages[0].content IS NOT NULL

UNION ALL

SELECT
    source.endpoint_name AS endpoint,
    request:messages[0].content AS prompt,
    response:choices[0].message.content AS model_response,
    input_token_count,
    output_token_count,
    request_time
FROM {catalog}.{schema}.`demo-gemini-3-1-pro_payload`
WHERE request:messages[0].content IS NOT NULL

ORDER BY prompt, endpoint
LIMIT 50;


-- ============================================================================
-- QUERY 4: Governance & Audit — All requests from a specific user
-- Demo point: "Full audit trail — who used what model, when, with what input."
-- ============================================================================

SELECT
    request_time,
    source.endpoint_name AS endpoint,
    request_metadata.requester AS user,
    request:messages[0].content AS prompt_preview,
    response:choices[0].message.content AS response_preview,
    input_token_count,
    output_token_count
FROM {catalog}.{schema}.`demo-claude-opus-4-6_payload`
WHERE request_time >= CURRENT_DATE - INTERVAL 7 DAYS
ORDER BY request_time DESC
LIMIT 50;
