from agent.graph.chat_graph import _contains_unsupported_standard_reference


def test_document_title_can_be_wrapped_in_book_title_marks():
    context = "来源：JGJ33-2012建筑机械使用安全技术规程；章节：第36页"
    assert not _contains_unsupported_standard_reference("依据《JGJ33-2012建筑机械使用安全技术规程》第36页。", context)


def test_unretrieved_title_and_clause_are_still_rejected():
    context = "来源：建筑机械使用安全技术规程；第三条"
    assert _contains_unsupported_standard_reference("依据《另一份施工安全规范》", context)
    assert _contains_unsupported_standard_reference("依据第九十九条", context)


def test_unretrieved_standard_number_is_still_rejected():
    assert _contains_unsupported_standard_reference("依据JGJ80-2016", "来源：JGJ33-2012建筑机械使用安全技术规程")
