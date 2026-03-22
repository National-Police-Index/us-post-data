import os
import tempfile

from pipeline.registry import Registry


def _reg(tmp, content):
    path = os.path.join(tmp, "registry.csv")
    with open(path, "w") as f:
        f.write("state,year,cleaned,firebase_pushed\n" + content)
    return Registry(path)


def test_is_cleaned_true():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,no\n")
        assert r.is_cleaned("xx", "2001") is True


def test_is_cleaned_false():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,no,no\n")
        assert r.is_cleaned("xx", "2001") is False
        assert r.is_cleaned("zz", "2001") is False


def test_firebase_pushed_values():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(
            d, "xx,2001,yes,yes\nxx,2002,yes,skipped\nxx,2003,no,no\n"
        )
        assert r.firebase_pushed("xx", "2001") == "yes"
        assert r.firebase_pushed("xx", "2002") == "skipped"
        assert r.firebase_pushed("xx", "2003") == "no"
        assert r.firebase_pushed("zz", "9999") == "no"  # unknown → default


def test_get_preseed_pairs_returns_cleaned_only():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(
            d, "xx,2001,yes,yes\nxx,2002,no,no\nyy,2001,yes,no\n"
        )
        pairs = r.get_preseed_pairs()
        assert ("xx", "2001") in pairs  # cleaned=yes
        assert ("yy", "2001") in pairs  # cleaned=yes
        assert ("xx", "2002") not in pairs  # cleaned=no


def test_upsert_new_row_persists():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "registry.csv")
        with open(path, "w") as f:
            f.write("state,year,cleaned,firebase_pushed\n")
        r = Registry(path)
        r.upsert("xx", "2001", cleaned="yes", firebase_pushed="no")
        r.save()
        assert Registry(path).is_cleaned("xx", "2001") is True


def test_get_firebase_target_returns_highest_unpushed():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,yes\nxx,2002,yes,no\nxx,2003,yes,no\n")
        assert r.get_firebase_target("xx") == "2003"  # highest unpushed


def test_get_firebase_target_none_when_all_pushed_or_uncleaned():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,yes\nxx,2002,no,no\n")
        assert r.get_firebase_target("xx") is None
