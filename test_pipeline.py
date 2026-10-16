from docustruct.pipeline import ExtractedTable, merge_tables, validate

def test_merge_continuation_and_repeated_header():
    x=ExtractedTable(["ID","Value"],[["1","10"],["2","20"]],[1])
    y=ExtractedTable(["ID","Value"],[["ID","Value"],["2","20"],["3","30"]],[2])
    merged=merge_tables([x,y])
    assert len(merged)==1
    assert merged[0].rows == [["1","10"],["2","20"],["3","30"]]

def test_total_mismatch():
    t=ExtractedTable(["Label","Amount"],[["A","10"],["B","20"],["Total","40"]],[1],name="Table_01")
    assert any("mismatch" in x["issue"] for x in validate([t]))
