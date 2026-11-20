from expense_bot import main


def test_check_hello(capsys):
    main()
    captured = capsys.readouterr()
    assert captured.out == "Hello from expense-bot!\n"
