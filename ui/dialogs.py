from PyQt5.QtWidgets import QMessageBox, QWidget


def show_error(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def show_info(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def confirm_flash(parent: QWidget, profile_name: str, warnings=()) -> bool:
    text = f"Flash the loaded BIN using profile:\n{profile_name}?"
    if warnings:
        text += "\n\nWarnings:\n" + "\n".join(f"• {w}" for w in warnings)
    text += "\n\nDo not disconnect power or the interface during an active write."
    answer = QMessageBox.warning(parent, "Confirm ECU Flash", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return answer == QMessageBox.Yes
