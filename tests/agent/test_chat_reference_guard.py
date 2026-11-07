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


def test_ordinary_chinese_list_enumeration_is_not_falsely_rejected():
    context = "现场施工应注意人员佩戴安全防护用具。"
    assert not _contains_unsupported_standard_reference(
        "安全建议如下：第一条，必须佩戴安全帽；第二条，禁止跨越临边防护栏。",
        context,
    )
    assert not _contains_unsupported_standard_reference(
        "第一条建议：加强临边巡查；第二条建议：落实班前交底。",
        context,
    )
    assert not _contains_unsupported_standard_reference(
        "共查询到2条隐患，第一条记录为高空未系安全带，第二条记录为无帽作业。",
        context,
    )
