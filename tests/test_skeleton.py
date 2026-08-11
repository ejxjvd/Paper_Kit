"""專案骨架冒煙測試：四層套件可匯入、NiceGUI 空殼可載入。"""


def test_four_layers_importable():
    from paper_kit import application, domain, infrastructure, presentation

    assert all(m.__name__ for m in (domain, application, infrastructure, presentation))


def test_nicegui_shell_imports():
    import nicegui

    assert nicegui.ui
