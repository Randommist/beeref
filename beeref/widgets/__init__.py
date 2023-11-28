# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os.path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.config import logfile_name, BeeSettings
from beeref.main_controls import MainControlsMixin
from beeref.widgets import settings  # noqa: F401


logger = logging.getLogger(__name__)


class RecentFilesModel(QtCore.QAbstractListModel):
    """An entry in the 'Recent Files' list."""

    def __init__(self, files):
        super().__init__()
        self.files = files

    def rowCount(self, parent):
        return len(self.files)

    def data(self, index, role):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return os.path.basename(self.files[index.row()])
        if role == QtCore.Qt.ItemDataRole.FontRole:
            font = QtGui.QFont()
            font.setUnderline(True)
            return font


class RecentFilesView(QtWidgets.QListView):

    def __init__(self, parent, files=None):
        super().__init__(parent)
        self.files = files or []
        self.clicked.connect(self.on_clicked)
        self.setModel(RecentFilesModel(self.files))
        self.setMouseTracking(True)

    def on_clicked(self, index):
        self.parent().parent().open_from_file(self.files[index.row()])

    def update_files(self, files):
        self.files = files
        self.model().files = files
        self.reset()

    def sizeHint(self):
        size = QtCore.QSize()
        height = sum(
            (self.sizeHintForRow(i) + 2) for i in range(len(self.files)))
        width = max(self.sizeHintForColumn(i) for i in range(len(self.files)))
        size.setHeight(height)
        size.setWidth(width + 2)
        return size

    def mouseMoveEvent(self, event):
        index = self.indexAt(
            QtCore.QPoint(int(event.position().x()),
                          int(event.position().y())))
        if index.isValid():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)


class WelcomeOverlay(MainControlsMixin, QtWidgets.QWidget):
    """Some basic info to be displayed when the scene is empty."""

    txt = """<p>Paste or drop images here.</p>
             <p>Right-click for more options.</p>"""

    def __init__(self, parent):
        super().__init__(parent)
        self.control_target = parent
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.init_main_controls(main_window=parent.parent)

        # Recent files
        self.files_layout = QtWidgets.QVBoxLayout()
        self.files_layout.addStretch(50)
        self.files_layout.addWidget(
            QtWidgets.QLabel('<h3>Recent Files</h3>', self))
        self.files_view = RecentFilesView(self)
        self.files_layout.addWidget(self.files_view)
        self.files_layout.addStretch(50)

        # Help text
        label = QtWidgets.QLabel(self.txt, self)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter
                           | Qt.AlignmentFlag.AlignCenter)
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addStretch(50)
        self.layout.addWidget(label)
        self.layout.addStretch(50)
        self.setLayout(self.layout)

    def show(self):
        files = BeeSettings().get_recent_files(existing_only=True)
        self.files_view.update_files(files)
        if files and self.layout.indexOf(self.files_layout) < 0:
            self.layout.insertLayout(0, self.files_layout)
        super().show()

    def mousePressEvent(self, event):
        if self.mousePressEventMainControls(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouseMoveEventMainControls(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mouseReleaseEventMainControls(event):
            return
        super().mouseReleaseEvent(event)


class BeeProgressDialog(QtWidgets.QProgressDialog):

    def __init__(self, label, worker, maximum=0, parent=None):
        super().__init__(label, 'Cancel', 0, maximum, parent=parent)
        logger.debug('Initialised progress bar')
        self.setMinimumDuration(0)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoReset(False)
        self.setAutoClose(False)
        worker.begin_processing.connect(self.on_begin_processing)
        worker.progress.connect(self.on_progress)
        worker.finished.connect(self.on_finished)
        self.canceled.connect(worker.on_canceled)

    def on_progress(self, value):
        logger.debug(f'Progress dialog: {value}')
        self.setValue(value)

    def on_begin_processing(self, value):
        logger.debug(f'Beginn progress dialog: {value}')
        self.setMaximum(value)

    def on_finished(self, filename, errors):
        logger.debug('Finished progress dialog')
        self.setValue(self.maximum())
        self.reset()
        self.hide()
        QtCore.QTimer.singleShot(100, self.deleteLater)


class HelpDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f'{constants.APPNAME} Help')
        docdir = os.path.join(os.path.dirname(__file__),
                              '..',
                              'documentation')
        tabs = QtWidgets.QTabWidget()

        # Controls
        with open(os.path.join(docdir, 'controls.html')) as f:
            controls_txt = f.read()
        controls = QtWidgets.QLabel(controls_txt)
        controls.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        tabs.addTab(scroll, '&Controls')

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(tabs)
        self.show()


class DebugLogDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f'{constants.APPNAME} Debug Log')
        with open(logfile_name()) as f:
            self.log_txt = f.read()

        self.log = QtWidgets.QPlainTextEdit(self.log_txt)
        self.log.setReadOnly(True)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self.copy_button = QtWidgets.QPushButton('Co&py To Clipboard')
        self.copy_button.released.connect(self.copy_to_clipboard)
        buttons.addButton(
            self.copy_button, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        name_widget = QtWidgets.QLabel(logfile_name())
        name_widget.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(name_widget)
        layout.addWidget(self.log)
        layout.addWidget(buttons)
        self.show()

    def copy_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.log_txt)


class SceneToPixmapExporterDialog(QtWidgets.QDialog):
    MIN_SIZE = 10
    MAX_SIZE = 100000

    def __init__(self, parent, default_size):
        super().__init__(parent)
        self.default_size = default_size
        if (self.default_size.width() > self.MAX_SIZE
                or self.default_size.width() >= self.MAX_SIZE):
            self.default_size.scale(
                self.MAX_SIZE, self.MAX_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio)

        self.ignore_change = False
        self.setWindowTitle('Export Scene to Image')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        width_label = QtWidgets.QLabel('Width:')
        layout.addWidget(width_label, 0, 0)
        self.width_input = QtWidgets.QSpinBox()
        self.width_input.setRange(self.MIN_SIZE, self.MAX_SIZE)
        self.width_input.setValue(default_size.width())
        self.width_input.valueChanged.connect(self.on_width_changed)
        layout.addWidget(self.width_input, 0, 1)

        height_label = QtWidgets.QLabel('Height:')
        layout.addWidget(height_label, 1, 0)
        self.height_input = QtWidgets.QSpinBox()
        self.height_input.setMinimum(10)
        self.height_input.setRange(self.MIN_SIZE, self.MAX_SIZE)
        self.height_input.setValue(default_size.height())
        self.height_input.valueChanged.connect(self.on_height_changed)
        layout.addWidget(self.height_input, 1, 1)

        # Bottom row of buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 3, 1)

    def on_width_changed(self, width):
        if not self.ignore_change:
            self.ignore_change = True
            new = self.default_size.scaled(
                width, self.MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
            self.height_input.setValue(new.height())
            self.ignore_change = False

    def on_height_changed(self, height):
        if not self.ignore_change:
            self.ignore_change = True
            new = self.default_size.scaled(
                self.MAX_SIZE, height, Qt.AspectRatioMode.KeepAspectRatio)
            self.width_input.setValue(new.width())
            self.ignore_change = False

    def value(self):
        return QtCore.QSize(self.width_input.value(),
                            self.height_input.value())
