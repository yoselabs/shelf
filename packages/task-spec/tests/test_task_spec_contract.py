from task_spec.testing import InMemoryAttentionStore, InMemoryTaskStore, attention_store_contract, task_store_contract


def test_the_in_memory_task_store_passes_the_task_store_contract() -> None:
    task_store_contract(InMemoryTaskStore)


def test_the_in_memory_attention_store_passes_the_attention_store_contract() -> None:
    attention_store_contract(InMemoryAttentionStore)
