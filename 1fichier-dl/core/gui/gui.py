import sys
import logging
import pickle
import os
import webbrowser
import PyQt5.sip
from ..download.workers import FilterWorker, DownloadWorker
from .themes import dark_theme
from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QPixmap
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGridLayout,
                             QPushButton, QSpinBox, QWidget, QMessageBox,
                             QTableView, QHeaderView, QHBoxLayout,
                             QPlainTextEdit, QVBoxLayout, QAbstractItemView,
                             QAbstractScrollArea, QLabel, QLineEdit,
                             QFileDialog, QProgressBar, QStackedWidget,
                             QFormLayout, QListWidget, QComboBox)

def absp(f):
    '''
    Get absolute path.
    '''
    path = os.path.join(os.path.dirname(__file__), '../..')
    return os.path.abspath(path + '/' + f)

def alert(text):
    '''
    Create and show QMessageBox Alert.
    '''
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle('Alert')
    msg.setText(text)
    msg.exec_()

def check_selection(table):
    '''
    Get selected rows from table.
    Returns list: [Rows]
    '''
    selection = []
    for index in table.selectionModel().selectedRows():
        selection.append(index.row())
    if not selection:
        alert('No rows were selected.')
    else:
        return selection

def create_file(f):
    '''
    Create empty file.
    [note] Used to create app/settings and app/cache.
    '''
    f = absp(f)
    logging.debug(f'Attempting to create file: {f}...')
    os.makedirs(os.path.dirname(f), exist_ok=True)
    f = open(f, 'x')
    f.close()

class GuiBehavior:
    def __init__(self, gui):
        self.filter_thread = QThreadPool()
        self.download_thread = QThreadPool()
        self.download_thread.setMaxThreadCount(1) # Limits concurrent downloads to 1.
        self.download_workers = []
        self.gui = gui
        self.handle_init()

    def handle_init(self):
        '''
        Load cached downloads.
        Create file in case it does not exist.
        '''
        try:
            with open(absp('app/cache'), 'rb') as f:
                self.cached_downloads = pickle.load(f)
                for download in self.cached_downloads:
                    self.gui.links = download[0]
                    self.add_links(True, download)
        except EOFError:
            self.cached_downloads = []
            logging.debug('No cached downloads.')
        except FileNotFoundError:
            self.cached_downloads = []
            create_file('app/cache')
        
        '''
        Load settings.
        Create file in case it doesn't exist.
        '''
        try:
            with open(absp('app/settings'), 'rb') as f:
                self.settings = pickle.load(f)
        except EOFError:
            self.settings = None
            logging.debug('No settings found.')
        except FileNotFoundError:
            self.settings = None
            create_file('app/settings')
                
    def resume_download(self):
        '''
        Resume selected downloads.
        '''
        selected_rows = check_selection(self.gui.table)

        if selected_rows:
            for i in selected_rows:
                if i < len(self.download_workers):
                    self.download_workers[i].resume()

    def stop_download(self):
        '''
        Stop selected downloads.
        '''
        selected_rows = check_selection(self.gui.table)

        if selected_rows:
            for i in reversed(selected_rows):
                if i < len(self.download_workers):
                    self.download_workers[i].stop(i)
                    self.download_workers.remove(self.download_workers[i])

    def pause_download(self):
        '''
        Pause selected downloads.
        '''
        selected_rows = check_selection(self.gui.table)

        if selected_rows:
            for i in selected_rows:
                if i < len(self.download_workers):
                    self.download_workers[i].signals.update_signal.emit(self.download_workers[i].data, [None, None, 'Paused', '0 B/s'])
                    self.download_workers[i].pause()

    def add_links(self, state, cached_download = ''):
        '''
        Calls FilterWorker()
        '''
        worker = FilterWorker(self, cached_download, (self.gui.password.text() if not cached_download else ''))

        worker.signals.download_signal.connect(self.download_receive_signal)
        worker.signals.alert_signal.connect(alert)
        
        self.filter_thread.start(worker)
    
    def download_receive_signal(self, row, link, append_row = True, dl_name = '', progress = 0):
        '''
        Append download to row and start download.
        '''
        if append_row:
            self.gui.table_model.appendRow(row)
            index = self.gui.table_model.index(self.gui.table_model.rowCount()-1, 4)
            progress_bar = QProgressBar()
            progress_bar.setValue(progress)
            self.gui.table.setIndexWidget(index, progress_bar)
            row[4] = progress_bar

        worker = DownloadWorker(link, self.gui.table_model, row, self.settings, dl_name)
        worker.signals.update_signal.connect(self.update_receive_signal)
        worker.signals.unpause_signal.connect(self.download_receive_signal)

        self.download_thread.start(worker)
        self.download_workers.append(worker)

    def update_receive_signal(self, data, items):
        '''
        Update download data.
        items = [File Name, Size, Down Speed, Progress, Pass]
        '''
        if data:
            if not PyQt5.sip.isdeleted(data[2]):
                for i in range(len(items)):
                    if items[i] and isinstance(items[i], str): data[i].setText(items[i])
                    if items[i] and not isinstance(items[i], str): data[i].setValue(items[i])
    
    def set_dl_directory(self):
        file_dialog = QFileDialog(self.gui.settings)
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.exec_()
        self.gui.dl_directory_input.setText(file_dialog.selectedFiles()[0])
    
    def change_theme(self, theme = None):
        '''
        Change app palette (theme).
        0 = Light
        1 = Dark
        '''
        if theme:
            self.gui.theme_select.setCurrentIndex(theme)

        if self.gui.theme_select.currentIndex() == 0:
            self.gui.app.setPalette(self.gui.main.style().standardPalette())
        elif self.gui.theme_select.currentIndex() == 1:
            self.gui.app.setPalette(dark_theme)


    def save_settings(self):
        with open(absp('app/settings'), 'wb') as f:
            settings = []
            settings.append(self.gui.dl_directory_input.text())   # Download Directory - 0
            settings.append(self.gui.theme_select.currentIndex()) # Theme              - 1
            settings.append(self.gui.timeout_input.value())       # Timeout            - 2
            settings.append(self.gui.proxy_settings_input.text()) # Proxy Settings     - 3
            pickle.dump(settings, f)
            self.settings = settings
        self.gui.settings.hide()
        
    def select_settings(self):
        '''
        Select settings page.
        '''
        selection = self.gui.settings_list.selectedIndexes()[0].row()
        self.gui.stacked_settings.setCurrentIndex(selection)


    def handle_exit(self):
        '''
        Save cached downloads data.
        '''
        active_downloads = []
        for w in self.download_workers:
            download = w.return_data()
            if download: active_downloads.append(download)
        active_downloads.extend(self.cached_downloads)

        with open(absp('app/cache'), 'wb') as f:
            if active_downloads:
                pickle.dump(active_downloads, f)
        
        os._exit(1)

class Gui:
    def __init__(self):
        # Init GuiBehavior()
        self.actions = GuiBehavior(self)
        self.app_name = '1Fichier Downloader v0.1.5'

        # Create App
        app = QApplication(sys.argv) 
        app.setWindowIcon(QIcon(absp('ico.ico')))
        app.setStyle('Fusion')
        app.aboutToQuit.connect(self.actions.handle_exit)

        self.app = app

        # Create Windows
        self.main_win()
        self.add_links_win()
        self.settings_win()

        # Change App Theme to saved one (Palette)
        if self.actions.settings:
            self.actions.change_theme(self.actions.settings[1])

        sys.exit(app.exec_())
    
    def main_win(self):
        # Define Main Window
        self.main = QMainWindow()
        self.main.setWindowTitle(self.app_name)
        widget = QWidget(self.main)
        self.main.setCentralWidget(widget)

        # Create Grid
        grid = QGridLayout()

        # Top Buttons
        download_btn = QPushButton(QIcon(absp('res/download.svg')), ' Add Link(s)')
        download_btn.clicked.connect(lambda: self.add_links.show() if not self.add_links.isVisible() else self.add_links.raise_())

        settings_btn = QPushButton(QIcon(absp('res/settings.svg')), ' Settings')
        settings_btn.clicked.connect(lambda: self.settings.show() if not self.settings.isVisible() else self.settings.raise_())

        # Table
        self.table = QTableView()
        headers = ['Name', 'Size', 'Status', 'Down Speed', 'Progress', 'Password']
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContentsOnFirstShow)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()

        self.table_model = QStandardItemModel()
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.table_model)

        # Append widgets to grid
        grid.addWidget(download_btn, 0, 0)
        grid.addWidget(settings_btn, 0, 1)
        grid.addWidget(self.table, 1, 0, 1, 2)

        # Bottom Buttons
        resume_btn = QPushButton(QIcon(absp('res/resume.svg')), ' Resume')
        resume_btn.clicked.connect(self.actions.resume_download)

        pause_btn = QPushButton(QIcon(absp('res/pause.svg')), ' Pause')
        pause_btn.clicked.connect(self.actions.pause_download)

        stop_btn = QPushButton(QIcon(absp('res/stop.svg')), ' Remove')
        stop_btn.clicked.connect(self.actions.stop_download)

        # Add buttons to Horizontal Layout
        hbox = QHBoxLayout()
        hbox.addWidget(resume_btn)
        hbox.addWidget(pause_btn)
        hbox.addWidget(stop_btn)

        self.main.setWindowFlags(self.main.windowFlags()
                                & Qt.CustomizeWindowHint)
                                
        grid.addLayout(hbox, 2, 0, 1, 2)
        widget.setLayout(grid)
        self.main.resize(670, 415)
        self.main.show()
    
    def add_links_win(self):
        # Define Add Links Win
        self.add_links = QMainWindow(self.main)
        self.add_links.setWindowTitle('Add Link(s)')
        widget = QWidget(self.add_links)
        self.add_links.setCentralWidget(widget)

        # Create Vertical Layout
        layout = QVBoxLayout()

        # Links input
        layout.addWidget(QLabel('Links:'))
        self.links = QPlainTextEdit()
        layout.addWidget(self.links)

        # Password input
        layout.addWidget(QLabel('Password:'))
        self.password = QLineEdit()
        layout.addWidget(self.password)

        # Add links
        add_btn = QPushButton('Add Link(s)')
        add_btn.clicked.connect(self.actions.add_links)
        layout.addWidget(add_btn)

        self.add_links.setMinimumSize(300, 200)
        widget.setLayout(layout)

    def settings_win(self):
        # Define Settings Win
        self.settings = QMainWindow(self.main)
        self.settings.setWindowTitle('Settings')

        # Create StackedWidget and Selection List
        self.stacked_settings = QStackedWidget()
        self.settings_list = QListWidget()
        self.settings_list.setFixedWidth(110)
        self.settings_list.addItems(['Behavior', 'Connection', 'About'])
        self.settings_list.clicked.connect(self.actions.select_settings)

        # Central Widget
        central_widget = QWidget()
        hbox = QHBoxLayout()
        hbox.addWidget(self.settings_list)
        hbox.addWidget(self.stacked_settings)
        central_widget.setLayout(hbox)
        self.settings.setCentralWidget(central_widget)

        '''
        Child widget
        Behavior Settings
        '''
        
        behavior_settings = QWidget()
        self.stacked_settings.addWidget(behavior_settings)

        # Main Layouts
        vbox = QVBoxLayout()
        vbox.setAlignment(Qt.AlignTop)
        form_layout = QFormLayout()

        # Change Directory
        form_layout.addRow(QLabel('Download directory:'))

        dl_directory_btn = QPushButton('Select..')
        dl_directory_btn.clicked.connect(self.actions.set_dl_directory)

        self.dl_directory_input = QLineEdit()
        if self.actions.settings is not None:
            self.dl_directory_input.setText(self.actions.settings[0])
        self.dl_directory_input.setDisabled(True)

        form_layout.addRow(dl_directory_btn, self.dl_directory_input)

        # Bottom Buttons
        save_settings = QPushButton('Save')
        save_settings.clicked.connect(self.actions.save_settings)

        # Change theme
        form_layout.addRow(QLabel('Theme:'))

        self.theme_select = QComboBox()
        self.theme_select.addItems(['Light', 'Dark'])
        self.theme_select.currentIndexChanged.connect(self.actions.change_theme)
        form_layout.addRow(self.theme_select)

        vbox.addLayout(form_layout)
        vbox.addStretch()
        vbox.addWidget(save_settings)
        behavior_settings.setLayout(vbox)

        '''
        Child widget
        Connection Settings
        '''
        
        connection_settings = QWidget()
        self.stacked_settings.addWidget(connection_settings)

        # Main Layouts
        vbox_c = QVBoxLayout()
        vbox_c.setAlignment(Qt.AlignTop)
        form_layout_c = QFormLayout()

        # Timeout
        form_layout_c.addRow(QLabel('Timeout:'))
        self.timeout_input = QSpinBox()
        if self.actions.settings is not None:
            self.timeout_input.setValue(self.actions.settings[2])
        else:
            self.timeout_input.setValue(30)

        form_layout_c.addRow(self.timeout_input)

        # Proxy settings
        form_layout_c.addRow(QLabel('Proxy settings:'))
        self.proxy_settings_input = QLineEdit()
        if self.actions.settings is not None:
            self.proxy_settings_input.setText(self.actions.settings[3])

        form_layout_c.addRow(self.proxy_settings_input)

        # Bottom buttons
        save_settings_c = QPushButton('Save')
        save_settings_c.clicked.connect(self.actions.save_settings)

        vbox_c.addLayout(form_layout_c)
        vbox_c.addStretch()
        vbox_c.addWidget(save_settings_c)
        connection_settings.setLayout(vbox_c)

        '''
        Child widget
        About
        '''

        about_settings = QWidget()
        self.stacked_settings.addWidget(about_settings)

        about_layout = QGridLayout()
        about_layout.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        logo.setPixmap(QPixmap(absp('res/zap.svg')))
        logo.setAlignment(Qt.AlignCenter)

        text = QLabel(self.app_name)
        text.setStyleSheet('font-weight: bold; color: #4256AD')

        github_btn = QPushButton(QIcon(absp('res/github.svg')), '')
        github_btn.setFixedWidth(32)
        github_btn.clicked.connect(lambda: webbrowser.open('https://github.com/manuGMG/1fichier-dl'))

        about_layout.addWidget(logo, 0, 0, 1, 0)
        about_layout.addWidget(github_btn, 1, 0)
        about_layout.addWidget(text, 1, 1)
        about_settings.setLayout(about_layout)
