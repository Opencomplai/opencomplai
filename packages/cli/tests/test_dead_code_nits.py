from opencomplai_cli import main


def test_print_human_removed():
    assert not hasattr(main, "_print_human")
