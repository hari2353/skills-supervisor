from skills_supervisor.consensus import majority_vote, self_consistency


def test_majority_winner():
    out = majority_vote(["yes", "yes", "no"])
    assert out["winner"] == "yes"
    assert out["counts"] == {"yes": 2, "no": 1}
    assert out["agreement"] == round(2 / 3, 4)


def test_tie_breaks_by_first_occurrence():
    out = majority_vote(["a", "b"])
    assert out["winner"] == "a"


def test_normalization():
    out = majority_vote([" Yes ", "yes", "NO"], normalize=lambda x: x.strip().lower())
    assert out["winner"] == "yes"
    assert out["original"] == " Yes "


def test_weighted_vote():
    out = majority_vote(["a", "b"], weights=[0.9, 0.2])
    assert out["winner"] == "a"
    assert out["weight_share"] == round(0.9 / 1.1, 4)


def test_self_consistency_consensus():
    out = self_consistency([["yes", "yes", "no"], ["yes", "no", "no"], ["yes", "yes", "yes"]])
    assert out["winner"] == "yes"
    assert out["consensus"] is True


def test_self_consistency_no_consensus():
    out = self_consistency([["a"], ["b"], ["c"]], threshold=0.6)
    assert out["consensus"] is False


def test_invalid_inputs():
    for answers in ([],):
        try:
            majority_vote(answers)
        except ValueError:
            continue
        raise AssertionError("empty accepted")
    try:
        majority_vote(["a", "b"], weights=[1.0])
    except ValueError:
        pass
    else:
        raise AssertionError("mismatched weights accepted")
    try:
        self_consistency([])
    except ValueError:
        pass
    else:
        raise AssertionError("empty samples accepted")
    try:
        self_consistency([["a"], []])
    except ValueError:
        pass
    else:
        raise AssertionError("empty inner sample accepted")
    try:
        self_consistency([["a"]], threshold=1.5)
    except ValueError:
        pass
    else:
        raise AssertionError("bad threshold accepted")
