alter table workflow_runs
add column if not exists llm_api_key_ciphertext text;
