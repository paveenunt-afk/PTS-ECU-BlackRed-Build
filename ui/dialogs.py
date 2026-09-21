from PyQt5.QtWidgets import QMessageBox, QWidget


def show_error(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def show_info(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def confirm_flash(parent: QWidget, profile_name: str, warnings=()) -> bool:
    text = f"ยืนยันการเขียนไฟล์ BIN ด้วยโปรไฟล์:\n{profile_name}?"
    if warnings:
        text += "\n\nคำเตือน:\n" + "\n".join(f"• {w}" for w in warnings)
    text += "\n\nห้ามตัดไฟหรือถอดอินเทอร์เฟซระหว่างเขียนข้อมูล"
    answer = QMessageBox.warning(parent, "ยืนยันการเขียน ECU", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return answer == QMessageBox.Yes
