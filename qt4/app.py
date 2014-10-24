#    Back In Time
#    Copyright (C) 2008-2014 Oprea Dan, Bart de Koning, Richard Bailey, Germar Reitze
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import os
import os.path
import stat
import sys

if not os.getenv( 'DISPLAY', '' ):
    os.putenv( 'DISPLAY', ':0.0' )

import datetime
import gettext
import time
import threading
import re

sys.path = [os.path.join( os.path.dirname( os.path.abspath( os.path.dirname( __file__ ) ) ), 'common' )] + sys.path

import backintime
import config
import tools
import logger
import snapshots
import guiapplicationinstance
import mount
import progress

from PyQt4.QtGui import *
from PyQt4.QtCore import *

import qt4tools
import settingsdialog
import snapshotsdialog
import logviewdialog
import restoredialog
import messagebox


_=gettext.gettext


class MainWindow( QMainWindow ):
    def __init__( self, config, app_instance, qapp ):
        QMainWindow.__init__( self )

        self.config = config
        self.app_instance = app_instance
        self.qapp = qapp
        self.snapshots = snapshots.Snapshots( config )
        self.last_take_snapshot_message = None

        #window icon
        import icon
        self.qapp.setWindowIcon(icon.BIT_LOGO)

        #main toolbar
        self.main_toolbar = self.addToolBar('main')
        self.main_toolbar.setFloatable( False )

        #profiles
        self.first_update_all = True
        self.disable_profile_changed = False
        self.combo_profiles = QComboBox( self )
        self.combo_profiles_action = self.main_toolbar.addWidget( self.combo_profiles )

        self.btn_take_snapshot = self.main_toolbar.addAction(icon.TAKE_SNAPSHOT, _('Take snapshot'))
        QObject.connect( self.btn_take_snapshot, SIGNAL('triggered()'), self.on_btn_take_snapshot_clicked )

        self.btn_update_snapshots = self.main_toolbar.addAction(icon.REFRESH_SNAPSHOT, _('Refresh snapshots list'))
        QObject.connect( self.btn_update_snapshots, SIGNAL('triggered()'), self.on_btn_update_snapshots_clicked )

        self.btn_name_snapshot = self.main_toolbar.addAction(icon.SNAPSHOT_NAME, _('Snapshot Name'))
        QObject.connect( self.btn_name_snapshot, SIGNAL('triggered()'), self.on_btn_name_snapshot_clicked )

        self.btn_remove_snapshot = self.main_toolbar.addAction(icon.REMOVE_SNAPSHOT, _('Remove Snapshot'))
        QObject.connect( self.btn_remove_snapshot, SIGNAL('triggered()'), self.on_btn_remove_snapshot_clicked )
    
        self.btn_snapshot_log_view = self.main_toolbar.addAction(icon.VIEW_SNAPSHOT_LOG, _('View Snapshot Log'))
        QObject.connect( self.btn_snapshot_log_view, SIGNAL('triggered()'), self.on_btn_snapshot_log_view_clicked )
    
        self.btn_log_view = self.main_toolbar.addAction(icon.VIEW_LAST_LOG, _('View Last Log'))
        QObject.connect( self.btn_log_view, SIGNAL('triggered()'), self.on_btn_log_view_clicked )
    
        self.main_toolbar.addSeparator()

        self.btn_settings = self.main_toolbar.addAction(icon.SETTINGS, _('Settings'))
        QObject.connect( self.btn_settings, SIGNAL('triggered()'), self.on_btn_settings_clicked )

        self.main_toolbar.addSeparator()

        self.btn_shutdown = self.main_toolbar.addAction(icon.SHUTDOWN, _('Shutdown'))
        self.btn_shutdown.setToolTip(_('Shutdown system after snapshot has finished.'))
        self.btn_shutdown.setCheckable(True)
        self.shutdown = tools.ShutDown()
        self.btn_shutdown.setEnabled(self.shutdown.can_shutdown())
        QObject.connect( self.btn_shutdown, SIGNAL('toggled(bool)'), self.on_btn_shutdown_toggled )

        self.btn_quit = self.main_toolbar.addAction(icon.EXIT, _('Exit'))
        self.btn_quit.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_W))
        QObject.connect( self.btn_quit, SIGNAL('triggered()'), self.close )

        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.main_toolbar.addWidget(empty)

        help_menu = QMenu()
        self.btn_help = help_menu.addAction(icon.HELP, _('Help') )
        QObject.connect( self.btn_help, SIGNAL('triggered()'), self.on_help )
        help_menu.addSeparator()
        self.btn_website = help_menu.addAction(icon.WEBSITE, _('Website') )
        QObject.connect( self.btn_website, SIGNAL('triggered()'), self.on_website)
        self.btn_changelog = help_menu.addAction(icon.CHANGELOG, _('Changelog') )
        QObject.connect( self.btn_changelog, SIGNAL('triggered()'), self.on_changelog)
        self.btn_faq = help_menu.addAction(icon.FAQ, _('FAQ') )
        QObject.connect( self.btn_faq, SIGNAL('triggered()'), self.on_faq)
        self.btn_question = help_menu.addAction(icon.QUESTION, _('Ask a question') )
        QObject.connect( self.btn_question, SIGNAL('triggered()'), self.on_ask_a_question)
        self.btn_bug = help_menu.addAction(icon.BUG, _('Report a bug') )
        QObject.connect( self.btn_bug, SIGNAL('triggered()'), self.on_report_a_bug)
        help_menu.addSeparator()
        self.btn_about = help_menu.addAction(icon.ABOUT, _('About') )
        QObject.connect( self.btn_about, SIGNAL('triggered()'), self.on_about)

        action = self.main_toolbar.addAction(icon.HELP, _('Help') )
        QObject.connect( action, SIGNAL('triggered()'), self.on_help )
        action.setMenu(help_menu)

        #main splitter
        self.main_splitter = QSplitter( self )
        self.main_splitter.setOrientation( Qt.Horizontal )

        #timeline
        self.list_time_line = QTreeWidget( self )
        self.list_time_line.setRootIsDecorated( False )
        self.list_time_line.setEditTriggers( QAbstractItemView.NoEditTriggers )
        self.list_time_line.setHeaderLabel( _('Snapshots') )
        self.list_time_line.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.main_splitter.addWidget( self.list_time_line )

        #right widget
        self.right_widget = QGroupBox( self )
        self.main_splitter.addWidget( self.right_widget )
        right_layout = QVBoxLayout( self.right_widget )
        left, top, right, bottom = right_layout.getContentsMargins()
        right_layout.setContentsMargins( 0, 0, right, 0 )

        #files toolbar
        self.files_view_toolbar = QToolBar( self )
        self.files_view_toolbar.setFloatable( False )

        self.btn_folder_up = self.files_view_toolbar.addAction(icon.UP, _('Up'))
        self.btn_folder_up.setShortcut(Qt.Key_Backspace)
        QObject.connect( self.btn_folder_up, SIGNAL('triggered()'), self.on_btn_folder_up_clicked )

        self.edit_current_path = QLineEdit( self )
        self.edit_current_path.setReadOnly( True )
        self.files_view_toolbar.addWidget( self.edit_current_path )

        #show hidden files
        self.show_hidden_files = self.config.get_bool_value( 'qt4.show_hidden_files', False )

        self.btn_show_hidden_files = self.files_view_toolbar.addAction(icon.SHOW_HIDDEN, _('Show hidden files'))
        self.btn_show_hidden_files.setCheckable( True )
        self.btn_show_hidden_files.setChecked( self.show_hidden_files )
        QObject.connect( self.btn_show_hidden_files, SIGNAL('toggled(bool)'), self.on_btn_show_hidden_files_toggled )

        self.files_view_toolbar.addSeparator()

        #restore menu
        self.menu_restore = QMenu()
        self.btn_restore = self.menu_restore.addAction(icon.RESTORE, _('Restore') )
        QObject.connect( self.btn_restore, SIGNAL('triggered()'), self.restore_this )
        self.btn_restore_to = self.menu_restore.addAction(icon.RESTORE_TO, _('Restore to ...') )
        QObject.connect( self.btn_restore_to, SIGNAL('triggered()'), self.restore_this_to )
        self.menu_restore_parent = self.menu_restore.addAction(icon.RESTORE, '' )
        QObject.connect( self.menu_restore_parent, SIGNAL('triggered()'), self.restore_parent )
        self.menu_restore_parent_to = self.menu_restore.addAction(icon.RESTORE_TO, '' )
        QObject.connect( self.menu_restore_parent_to, SIGNAL('triggered()'), self.restore_parent_to )

        self.btn_restore_menu = self.files_view_toolbar.addAction(icon.RESTORE, _('Restore'))
        self.btn_restore_menu.setMenu(self.menu_restore)
        QObject.connect( self.btn_restore_menu, SIGNAL('triggered()'), self.restore_this )

        self.btn_snapshots = self.files_view_toolbar.addAction(icon.SNAPSHOTS, _('Snapshots'))
        QObject.connect( self.btn_snapshots, SIGNAL('triggered()'), self.on_btn_snapshots_clicked )

        right_layout.addWidget( self.files_view_toolbar )

        #menubar
        self.menubar = self.menuBar()
        self.menubar_snapshot = self.menubar.addMenu(_('Snapshot'))
        self.menubar_snapshot.addAction(self.btn_take_snapshot)
        self.menubar_snapshot.addAction(self.btn_update_snapshots)
        self.menubar_snapshot.addAction(self.btn_name_snapshot)
        self.menubar_snapshot.addAction(self.btn_remove_snapshot)
        self.menubar_snapshot.addSeparator()
        self.menubar_snapshot.addAction(self.btn_settings)
        self.menubar_snapshot.addSeparator()
        self.menubar_snapshot.addAction(self.btn_shutdown)
        self.menubar_snapshot.addAction(self.btn_quit)

        self.menubar_view = self.menubar.addMenu(_('View'))
        self.menubar_view.addAction(self.btn_folder_up)
        self.menubar_view.addAction(self.btn_show_hidden_files)
        self.menubar_view.addSeparator()
        self.menubar_view.addAction(self.btn_snapshot_log_view)
        self.menubar_view.addAction(self.btn_log_view)
        self.menubar_view.addSeparator()
        self.menubar_view.addAction(self.btn_snapshots)

        self.menubar_restore = self.menubar.addMenu(_('Restore'))
        self.menubar_restore.addAction(self.btn_restore)
        self.menubar_restore.addAction(self.btn_restore_to)
        self.menubar_restore.addAction(self.menu_restore_parent)
        self.menubar_restore.addAction(self.menu_restore_parent_to)

        self.menubar_help = self.menubar.addMenu(_('Help'))
        self.menubar_help.addAction(self.btn_help)
        self.menubar_help.addSeparator()
        self.menubar_help.addAction(self.btn_website)
        self.menubar_help.addAction(self.btn_changelog)
        self.menubar_help.addAction(self.btn_faq)
        self.menubar_help.addAction(self.btn_question)
        self.menubar_help.addAction(self.btn_bug)
        self.menubar_help.addSeparator()
        self.menubar_help.addAction(self.btn_about)

        #second spliter
        self.second_splitter = QSplitter( self )
        self.second_splitter.setOrientation( Qt.Horizontal )
        self.second_splitter.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget( self.second_splitter )

        #places
        self.list_places = QTreeWidget( self )
        self.list_places.setRootIsDecorated( False )
        self.list_places.setEditTriggers( QAbstractItemView.NoEditTriggers )
        self.list_places.setHeaderLabel(  _('Shortcuts') )
        self.second_splitter.addWidget( self.list_places )

        #files view stacked layout
        widget = QWidget( self )
        self.files_view_layout = QStackedLayout( widget )
        self.second_splitter.addWidget( widget )

        #folder don't exist label
        self.lbl_folder_dont_exists = QLabel( _('This folder doesn\'t exist\nin the current snapshot !'), self )
        qt4tools.set_font_bold( self.lbl_folder_dont_exists )
        self.lbl_folder_dont_exists.setFrameShadow( QFrame.Sunken )
        self.lbl_folder_dont_exists.setFrameShape( QFrame.Panel )
        self.lbl_folder_dont_exists.setAlignment( Qt.AlignHCenter | Qt.AlignVCenter )
        self.files_view_layout.addWidget( self.lbl_folder_dont_exists )

        #list files view
        self.list_files_view = QTreeView( self )
        self.files_view_layout.addWidget( self.list_files_view )
        self.list_files_view.setRootIsDecorated( False )
        self.list_files_view.setAlternatingRowColors( True )
        self.list_files_view.setEditTriggers( QAbstractItemView.NoEditTriggers )
        self.list_files_view.setItemsExpandable( False )
        self.list_files_view.setDragEnabled( False )

        self.list_files_view_header = self.list_files_view.header()
        self.list_files_view_header.setClickable( True )
        self.list_files_view_header.setMovable( False )
        self.list_files_view_header.setSortIndicatorShown( True )

        self.list_files_view_model = QFileSystemModel()
        self.list_files_view_model.setRootPath(QDir().rootPath())
        self.list_files_view_model.setReadOnly(True)
        self.list_files_view_model.setFilter(QDir.AllDirs | QDir.AllEntries
                                            | QDir.NoDotAndDotDot | QDir.Hidden)

        self.list_files_view_proxy_model = QSortFilterProxyModel()
        self.list_files_view_proxy_model.setDynamicSortFilter(True)
        self.list_files_view_proxy_model.setSourceModel(self.list_files_view_model)

        self.list_files_view.setModel(self.list_files_view_proxy_model)

        self.list_files_view_delegate = QStyledItemDelegate( self )
        self.list_files_view.setItemDelegate( self.list_files_view_delegate )

        sort_column = self.config.get_int_value( 'qt4.main_window.files_view.sort.column', 0 )
        sort_order = self.config.get_bool_value( 'qt4.main_window.files_view.sort.ascending', True )
        if sort_order:
            sort_order = Qt.AscendingOrder
        else:
            sort_order = Qt.DescendingOrder

        self.list_files_view_header.setSortIndicator( sort_column, sort_order )
        self.list_files_view_model.sort(self.list_files_view_header.sortIndicatorSection(),
                                        self.list_files_view_header.sortIndicatorOrder() )
        QObject.connect(self.list_files_view_header,
                        SIGNAL('sortIndicatorChanged(int,Qt::SortOrder)'),
                        self.list_files_view_model.sort )

        self.files_view_layout.setCurrentWidget( self.list_files_view )

        #
        self.setCentralWidget( self.main_splitter )

        #context menu
        self.list_files_view.setContextMenuPolicy(Qt.CustomContextMenu)
        QObject.connect(self.list_files_view, SIGNAL('customContextMenuRequested(const QPoint&)'), self.on_context_menu)
        self.contextMenu = QMenu(self)
        self.contextMenu.addAction(self.btn_restore)
        self.contextMenu.addAction(self.btn_restore_to)
        self.contextMenu.addAction(self.btn_snapshots)
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(self.btn_show_hidden_files)

        #ProgressBar
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.progressBar.setStyleSheet("text-align: left;")
        self.progressBar.setVisible(False)
        self.status = QLabel()

        self.statusBar().addWidget(self.progressBar, 100)
        self.statusBar().addWidget(self.status, 100)
        self.status.setText( _('Done') )

        self.snapshots_list = []
        self.snapshot_id = '/'
        self.path = self.config.get_profile_str_value('qt4.last_path',
                            self.config.get_str_value('qt4.last_path', '/' ) )
        self.edit_current_path.setText( self.path )

        #restore size and position
        x = self.config.get_int_value( 'qt4.main_window.x', -1 )
        y = self.config.get_int_value( 'qt4.main_window.y', -1 )
        if x >= 0 and y >= 0:
            self.move( x, y )

        w = self.config.get_int_value( 'qt4.main_window.width', 800 )
        h = self.config.get_int_value( 'qt4.main_window.height', 500 )
        self.resize( w, h )

        main_splitter_left_w = self.config.get_int_value( 'qt4.main_window.main_splitter_left_w', 150 )
        main_splitter_right_w = self.config.get_int_value( 'qt4.main_window.main_splitter_right_w', 450 )
        sizes = [ main_splitter_left_w, main_splitter_right_w ]
        self.main_splitter.setSizes( sizes )
        
        second_splitter_left_w = self.config.get_int_value( 'qt4.main_window.second_splitter_left_w', 150 )
        second_splitter_right_w = self.config.get_int_value( 'qt4.main_window.second_splitter_right_w', 300 )
        sizes = [ second_splitter_left_w, second_splitter_right_w ]
        self.second_splitter.setSizes( sizes )

        files_view_name_width = self.config.get_int_value( 'qt4.main_window.files_view.name_width', -1 )
        files_view_size_width = self.config.get_int_value( 'qt4.main_window.files_view.size_width', -1 )
        files_view_date_width = self.config.get_int_value( 'qt4.main_window.files_view.date_width', -1 )
        if files_view_name_width > 0 and files_view_size_width > 0 and files_view_date_width > 0:
            self.list_files_view_header.resizeSection( 0, files_view_name_width )
            self.list_files_view_header.resizeSection( 1, files_view_size_width )
            self.list_files_view_header.resizeSection( 2, files_view_date_width )

        #force settingdialog if it is not configured
        if not cfg.is_configured():
            message = _('%(appName)s is not configured. Would you like '
                        'to restore a previous configuration?' % {'appName': self.config.APP_NAME})
            if QMessageBox.Yes == messagebox.warningYesNo(self, message):
                settingsdialog.RestoreConfigDialog(self).exec_()
            settingsdialog.SettingsDialog( self ).exec_()

        if not cfg.is_configured():
            return
    
        if self.snapshots.has_old_snapshots():
            settingsdialog.SettingsDialog( self ).update_snapshots_location()

        profile_id = cfg.get_current_profile()
        
        #mount
        try:
            mnt = mount.Mount(cfg = self.config, profile_id = profile_id, parent = self)
            hash_id = mnt.mount()
        except mount.MountException as ex:
            messagebox.critical( self, str(ex) )
        else:
            self.config.set_current_hash_id(hash_id)
        
        if not cfg.can_backup( profile_id ):
            messagebox.critical( self, _('Can\'t find snapshots folder.\nIf it is on a removable drive please plug it and then press OK') )

        QObject.connect(self.list_files_view_proxy_model, SIGNAL('layoutChanged()'), self.on_dir_lister_completed)

        #populate lists
        self.update_profiles()
        QObject.connect( self.combo_profiles, SIGNAL('currentIndexChanged(int)'), self.on_profile_changed )

        self.list_files_view.setFocus()

        self.update_snapshot_actions()

        QObject.connect( self.list_time_line, SIGNAL('itemSelectionChanged()'), self.on_list_time_line_current_item_changed )
        QObject.connect( self.list_places, SIGNAL('currentItemChanged(QTreeWidgetItem*,QTreeWidgetItem*)'), self.on_list_places_current_item_changed )
        QObject.connect( self.list_files_view, SIGNAL('activated(const QModelIndex&)'), self.on_list_files_view_item_activated )

        self.force_wait_lock_counter = 0
    
        self.timer_raise_application = QTimer( self )
        self.timer_raise_application.setInterval( 1000 )
        self.timer_raise_application.setSingleShot( False )
        QObject.connect( self.timer_raise_application, SIGNAL('timeout()'), self.raise_application )
        self.timer_raise_application.start()

        self.timer_update_take_snapshot = QTimer( self )
        self.timer_update_take_snapshot.setInterval( 1000 )
        self.timer_update_take_snapshot.setSingleShot( False )
        QObject.connect( self.timer_update_take_snapshot, SIGNAL('timeout()'), self.update_take_snapshot )
        self.timer_update_take_snapshot.start()

    def closeEvent( self, event ):
        if self.shutdown.ask_before_quit():
            if QMessageBox.Yes != messagebox.warningYesNo(self, _('If you close this window Back In Time will not be able to shutdown your system when the snapshot has finished.\nDo you really want to close?') ):
                return event.ignore()

        self.config.set_str_value( 'qt4.last_path', self.path )
        self.config.set_profile_str_value('qt4.last_path', self.path)

        self.config.set_int_value( 'qt4.main_window.x', self.x() )
        self.config.set_int_value( 'qt4.main_window.y', self.y() )
        self.config.set_int_value( 'qt4.main_window.width', self.width() )
        self.config.set_int_value( 'qt4.main_window.height', self.height() )

        sizes = self.main_splitter.sizes()
        self.config.set_int_value( 'qt4.main_window.main_splitter_left_w', sizes[0] )
        self.config.set_int_value( 'qt4.main_window.main_splitter_right_w', sizes[1] )
    
        sizes = self.second_splitter.sizes()
        self.config.set_int_value( 'qt4.main_window.second_splitter_left_w', sizes[0] )
        self.config.set_int_value( 'qt4.main_window.second_splitter_right_w', sizes[1] )

        self.config.set_int_value( 'qt4.main_window.files_view.name_width', self.list_files_view_header.sectionSize( 0 ) )
        self.config.set_int_value( 'qt4.main_window.files_view.size_width', self.list_files_view_header.sectionSize( 1 ) )
        self.config.set_int_value( 'qt4.main_window.files_view.date_width', self.list_files_view_header.sectionSize( 2 ) )

        self.config.set_bool_value( 'qt4.show_hidden_files', self.show_hidden_files )

        self.config.set_int_value( 'qt4.main_window.files_view.sort.column', self.list_files_view_header.sortIndicatorSection() )
        self.config.set_bool_value( 'qt4.main_window.files_view.sort.ascending', self.list_files_view_header.sortIndicatorOrder() == Qt.AscendingOrder )

        self.list_files_view_model.deleteLater()

        #umount
        try:
            mnt = mount.Mount(cfg = self.config, parent = self)
            mnt.umount(self.config.current_hash_id)
        except mount.MountException as ex:
            messagebox.critical( self, str(ex) )
            
        self.config.save()

        event.accept()

    def update_profiles( self ):
        if self.disable_profile_changed:
            return

        self.disable_profile_changed = True

        self.combo_profiles.clear()

        index = 0
        profiles = self.config.get_profiles_sorted_by_name()

        for profile_id in profiles:
            if profile_id == self.config.get_current_profile():
                index = self.combo_profiles.count()
            self.combo_profiles.addItem( self.config.get_profile_name( profile_id ), profile_id )

        self.combo_profiles.setCurrentIndex( index )
        self.combo_profiles_action.setVisible( len( profiles ) > 1 )

        self.update_profile()

        self.disable_profile_changed = False

    def update_profile( self ):
        self.update_time_line()
        self.update_places()
        self.update_files_view( 0 )

    def on_profile_changed( self, index ):
        if self.disable_profile_changed:
            return

        profile_id = str( self.combo_profiles.itemData( index ) )
        if not profile_id:
            return
        old_profile_id = self.config.get_current_profile()
        if profile_id != old_profile_id:
            self.remount(profile_id, old_profile_id)
            self.config.set_current_profile( profile_id )

            self.config.set_profile_str_value('qt4.last_path', self.path, old_profile_id)
            path = self.config.get_profile_str_value('qt4.last_path', self.path, profile_id)
            if not path == self.path:
                self.path = path
                self.edit_current_path.setText( self.path )

            self.update_profile()
            
    def remount( self, new_profile_id, old_profile_id):
        try:
            mnt = mount.Mount(cfg = self.config, profile_id = old_profile_id, parent = self)
            hash_id = mnt.remount(new_profile_id)
        except mount.MountException as ex:
            messagebox.critical( self, str(ex) )
        else:
            self.config.set_current_hash_id(hash_id)

    def get_default_startup_folder_and_file( self ):
        last_path = self.config.get_str_value( 'gnome.last_path', '' )
        if last_path and os.path.isdir(last_path):
            return ( last_path, None, False )
        return ( '/', None, False )

    def get_cmd_startup_folder_and_file( self, cmd ):
        if cmd is None:
            cmd = self.app_instance.raise_cmd

        if not cmd:
            return None

        path = None
        show_snapshots = False

        for arg in cmd.split( '\n' ):
            if not arg:
                continue
            if arg == '-s' or arg == '--snapshots':
                show_snapshots = True
                continue
            if arg.startswith('-'):
                continue
            if path is None:
                path = arg

        if path is None:
            return None

        if not path:
            return None

        path = os.path.expanduser( path )
        path = os.path.abspath( path )

        if os.path.isdir( path ):
            if not path:
                show_snapshots = False

            if show_snapshots:
                return ( os.path.dirname( path ), path, True )
            else:
                return ( path, '', False )

        if os.path.isfile( path ):
            return ( os.path.dirname( path ), path, show_snapshots )

        return None

    def get_startup_folder_and_file( self, cmd = None ):
        startup_folder = self.get_cmd_startup_folder_and_file( cmd )
        if startup_folder is None:
            return self.get_default_startup_folder_and_file()
        return startup_folder

    def raise_application( self ):
        raise_cmd = self.app_instance.raise_command()
        if raise_cmd is None:
            return
        
        print("Raise cmd: " + raise_cmd)
        self.qapp.alert( self )

    def update_take_snapshot( self, force_wait_lock = False ):
        if force_wait_lock:
            self.force_wait_lock_counter = 10
        
        busy = self.snapshots.is_busy()
        if busy:
            self.force_wait_lock_counter = 0

        if self.force_wait_lock_counter > 0:
            self.force_wait_lock_counter = self.force_wait_lock_counter - 1

        fake_busy = busy or self.force_wait_lock_counter > 0

        message = _('Working:')
        take_snapshot_message = self.snapshots.get_take_snapshot_message()
        if fake_busy:
            if take_snapshot_message is None:
                take_snapshot_message = ( 0, '...' )
        elif take_snapshot_message is None:
            take_snapshot_message = self.last_take_snapshot_message
            if take_snapshot_message is None:
                take_snapshot_message = ( 0, _('Done') )

        force_update = False

        if fake_busy:
            if self.btn_take_snapshot.isEnabled():
                self.btn_take_snapshot.setEnabled( False )
        elif not self.btn_take_snapshot.isEnabled():
            force_update = True

            self.btn_take_snapshot.setEnabled( True )
            
            snapshots_list = self.snapshots.get_snapshots_and_other_list()

            if snapshots_list != self.snapshots_list:
                self.snapshots_list = snapshots_list
                self.update_time_line( False )
                take_snapshot_message = ( 0, _('Done') )
            else:
                if take_snapshot_message[0] == 0:
                    take_snapshot_message = ( 0, _('Done, no backup needed') )

            self.shutdown.shutdown()

        if take_snapshot_message != self.last_take_snapshot_message or force_update:
            self.last_take_snapshot_message = take_snapshot_message

            if fake_busy:
                message = _('Working:') + ' ' + self.last_take_snapshot_message[1].replace( '\n', ' ' )
            elif take_snapshot_message[0] == 0:
                message = self.last_take_snapshot_message[1].replace( '\n', ' ' )
            else:
                message = _('Error:') + ' ' + self.last_take_snapshot_message[1].replace( '\n', ' ' )

            self.status.setText(message)

        pg = progress.ProgressFile(self.config)
        if pg.isFileReadable():
            self.progressBar.setVisible(True)
            self.status.setVisible(False)
            pg.load()
            self.progressBar.setValue(pg.get_int_value('percent') )
            self.progressBar.setFormat(' | '.join(self.getProgressBarFormat(pg, self.status.text())) )
        else:
            self.progressBar.setVisible(False)
            self.status.setVisible(True)

        #if not fake_busy:
        #	self.last_take_snapshot_message = None

    def getProgressBarFormat(self, pg, message):
        d = (('sent',   _('Sent:')), \
             ('speed',  _('Speed:')),\
             ('eta',    _('ETA:')) )
        yield ' %p%'
        for key, txt in d:
            value = pg.get_str_value(key, '')
            if not value:
                continue
            yield txt + ' ' + value
        yield message

    def on_list_places_current_item_changed( self, item, previous ):
        if item is None:
            return

        path = str( item.data( 0, Qt.UserRole ) )
        if not path:
            return

        if path == self.path:
            return

        self.path = path
        self.update_files_view( 3 )

    def add_place( self, name, path, icon ):
        item = QTreeWidgetItem()

        item.setText( 0, name )

        if icon:
            item.setIcon( 0, QIcon.fromTheme( icon ) )

        item.setData( 0, Qt.UserRole, path )

        if not path:
            item.setFont( 0, qt4tools.get_font_bold( item.font( 0 ) ) )
            item.setFlags( Qt.ItemIsEnabled )
            item.setBackgroundColor( 0, QColor( 196, 196, 196 ) )
            item.setTextColor( 0, QColor( 60, 60, 60 ))

        self.list_places.addTopLevelItem( item )

        if path == self.path:
            self.list_places.setCurrentItem( item )

        return item

    def update_places( self ):
        self.list_places.clear()
        self.add_place( _('Global'), '', '' )
        self.add_place( _('Root'), '/', 'computer' )
        self.add_place( _('Home'), os.path.expanduser( '~' ), 'user-home' )

        #add backup folders
        include_folders = self.config.get_include()
        if include_folders:
            folders = []
            for item in include_folders:
                if item[1] == 0:
                    folders.append( item[0] )

            if folders:
                self.add_place( _('Backup folders'), '', '' )
                for folder in folders:
                    self.add_place( folder, folder, 'document-save' )

    def update_snapshot_actions( self, item = None ):
        enabled = False

        if item is None:
            item = self.get_list_time_line_selection()
        if not item is None:
            if len( self.time_line_get_snapshot_id( item ) ) > 1:
                enabled = True

        #update remove/name snapshot buttons
        self.btn_name_snapshot.setEnabled( enabled )
        self.btn_remove_snapshot.setEnabled( enabled )
        self.btn_snapshot_log_view.setEnabled( enabled )

    def get_list_time_line_selection( self, multiSelection = False):
        if multiSelection:
            return self.list_time_line.selectedItems()
        return self.list_time_line.currentItem()

    def on_list_time_line_current_item_changed(self):
        item = self.get_list_time_line_selection()
        self.update_snapshot_actions(item)

        if item is None:
            return

        snapshot_id = self.time_line_get_snapshot_id( item )
        if not snapshot_id:
            return

        if snapshot_id == self.snapshot_id:
            return

        self.snapshot_id = snapshot_id
        self.update_files_view( 2 )

    def time_line_get_snapshot_id( self, item ):
        return str( item.data( 0, Qt.UserRole ) ) 

    def time_line_update_snapshot_name( self, item ):
        snapshot_id = self.time_line_get_snapshot_id( item )
        if snapshot_id:
            item.setText( 0, self.snapshots.get_snapshot_display_name( snapshot_id ) )

    def add_time_line( self, snapshot_name, snapshot_id, tooltip = None):
        item = QTreeWidgetItem()
        item.setText( 0, snapshot_name )
        item.setFont( 0, qt4tools.get_font_normal( item.font( 0 ) ) )
        item.setData( 0, Qt.UserRole, snapshot_id )
        if not tooltip is None:
            item.setToolTip(0, tooltip)

        if not snapshot_id:
            item.setFont( 0, qt4tools.get_font_bold( item.font( 0 ) ) )
            item.setFlags( Qt.ItemIsEnabled )
            item.setBackgroundColor( 0, QColor( 196, 196, 196 ) )
            item.setTextColor( 0, QColor( 60, 60, 60 ) )

        self.list_time_line.addTopLevelItem( item )

        return item

    def update_time_line( self, get_snapshots_list = True ):
        self.list_time_line.clear()
        self.add_time_line( self.snapshots.get_snapshot_display_name( '/' ), '/' )

        if get_snapshots_list:
            self.snapshots_list = self.snapshots.get_snapshots_and_other_list() 

        groups = []
        now = datetime.date.today()

        #today
        date = now
        groups.append( ( _('Today'), self.snapshots.get_snapshot_id( date ), []) )

        #yesterday
        date = now - datetime.timedelta( days = 1 )
        groups.append( ( _('Yesterday'), self.snapshots.get_snapshot_id( date ), []) )

        #this week
        date = now - datetime.timedelta( days = now.weekday() )
        groups.append( ( _('This week'), self.snapshots.get_snapshot_id( date ), []) )

        #last week
        date = now - datetime.timedelta( days = now.weekday() + 7 )
        groups.append( ( _('Last week'), self.snapshots.get_snapshot_id( date ), []) )

        #fill groups
        for snapshot_id in self.snapshots_list:
            found = False

            for group in groups:
                if snapshot_id >= group[1]:
                    group[2].append( snapshot_id )
                    found = True
                    break

            if not found:
                year = int( snapshot_id[ 0 : 4 ] )
                month = int( snapshot_id[ 4 : 6 ] )
                date = datetime.date( year, month, 1 )

                group_name = ''
                if year == now.year:
                    group_name = date.strftime( '%B' ).capitalize()
                else:
                    group_name = date.strftime( '%B, %Y' ).capitalize()

                groups.append( ( group_name, self.snapshots.get_snapshot_id( date ), [ snapshot_id ]) )

        #fill time_line list
        for group in groups:
            if group[2]:
                self.add_time_line( group[0], '' );
                for snapshot_id in group[2]:
                    list_item = self.add_time_line( self.snapshots.get_snapshot_display_name( snapshot_id ),
                                                    snapshot_id,
                                                    _('Last check %s') %
                                                    self.snapshots.get_snapshot_last_check(snapshot_id) )
                    if snapshot_id == self.snapshot_id:
                        self.list_time_line.setCurrentItem( list_item )

        if self.list_time_line.currentItem() is None:
            self.list_time_line.setCurrentItem( self.list_time_line.topLevelItem( 0 ) )
            if self.snapshot_id != '/':
                self.snapshot_id = '/'
                self.update_files_view( 2 )

    def on_btn_take_snapshot_clicked( self ):
        backintime.take_snapshot_now_async( self.config )
        self.update_take_snapshot( True )

    def on_btn_update_snapshots_clicked( self ):
        self.update_time_line()
        self.update_files_view( 2 )

    def on_btn_name_snapshot_clicked( self ):
        item = self.list_time_line.currentItem()
        if item is None:
            return

        snapshot_id = self.time_line_get_snapshot_id( item )
        if len( snapshot_id ) <= 1:
            return

        name = self.snapshots.get_snapshot_name( snapshot_id )

        ret_val = QInputDialog.getText(self, _('Snapshot Name'), str() )
        if not ret_val[1]:
            return
        
        new_name = ret_val[0].strip()
        if name == new_name:
            return

        self.snapshots.set_snapshot_name( snapshot_id, new_name )
        self.time_line_update_snapshot_name( item )

    def on_btn_log_view_clicked ( self ):
        logviewdialog.LogViewDialog( self ).exec_()

    def on_btn_snapshot_log_view_clicked ( self ):
        item = self.list_time_line.currentItem()
        if item is None:
            return

        snapshot_id = self.time_line_get_snapshot_id( item )
        if len( snapshot_id ) <= 1:
            return

        logviewdialog.LogViewDialog( self, snapshot_id ).exec_()

    def on_btn_remove_snapshot_clicked ( self ):
        snapshot_ids = [self.time_line_get_snapshot_id(item) \
                        for item in self.get_list_time_line_selection(True) \
                        if len(self.time_line_get_snapshot_id(item)) > 1]
        if not snapshot_ids:
            return
        
        if QMessageBox.Yes != messagebox.warningYesNo( self, \
                            _('Are you sure you want to remove the snapshot:\n%s') % \
                            '\n'.join([self.snapshots.get_snapshot_display_name( snapshot_id ) \
                            for snapshot_id in snapshot_ids]) ):
            return

        #inhibit suspend/hibernate during delete
        self.config.inhibitCookie = tools.inhibitSuspend(toplevel_xid = self.config.xWindowId,
                                                         reason = 'deleting snapshots')

        [self.snapshots.remove_snapshot( snapshot_id ) for snapshot_id in snapshot_ids]
        self.update_time_line()

        #release inhibit suspend
        if self.config.inhibitCookie:
            tools.unInhibitSuspend(self.config.inhibitCookie)

    def on_btn_settings_clicked( self ):
        if QDialog.Accepted == settingsdialog.SettingsDialog( self ).exec_():
            profile_id = self.config.get_current_profile()
            self.remount(profile_id, profile_id)
            self.update_profiles()

    def on_btn_shutdown_toggled(self, checked):
        self.shutdown.activate_shutdown = checked

    def on_context_menu(self, point):
        self.contextMenu.exec_(self.list_files_view.mapToGlobal(point) )

    def on_about( self ):
        dlg = About(self)
        dlg.exec_()

    def on_help( self ):
        self.open_url( 'http://backintime.le-web.org/documentation' );

    def on_website( self ):
        self.open_url( 'http://backintime.le-web.org' );

    def on_changelog( self ):
        self.open_url( 'http://backintime.le-web.org/change-log' )

    def on_faq( self ):
        self.open_url( 'https://answers.launchpad.net/backintime/+faqs' );

    def on_ask_a_question( self ):
        self.open_url( 'https://answers.launchpad.net/backintime' );

    def on_report_a_bug( self ):
        self.open_url( 'https://bugs.launchpad.net/backintime' );

    def open_url( self, url ):
        return QDesktopServices.openUrl(QUrl(url))

    def on_btn_show_hidden_files_toggled( self, checked ):
        self.show_hidden_files = checked
        self.update_files_view( 1 )

    def restore_this( self ):
        if len( self.snapshot_id ) <= 1:
            return

        selected_file, idx = self.file_selected()
        if not selected_file:
            return

        rel_path = os.path.join( self.path, selected_file )
        restoredialog.restore( self, self.snapshot_id, rel_path )

    def restore_this_to( self ):
        if len( self.snapshot_id ) <= 1:
            return

        selected_file, idx = self.file_selected()
        if not selected_file:
            return

        rel_path = os.path.join( self.path, selected_file )
        restoredialog.restore( self, self.snapshot_id, rel_path, None )

    def restore_parent( self ):
        if len( self.snapshot_id ) <= 1:
            return
        restoredialog.restore( self, self.snapshot_id, self.path)

    def restore_parent_to( self ):
        if len( self.snapshot_id ) <= 1:
            return
        restoredialog.restore( self, self.snapshot_id, self.path, None )

    def on_btn_snapshots_clicked( self ):
        selected_file, idx = self.file_selected()
        if not selected_file:
            return

        rel_path = os.path.join( self.path, selected_file )

        dlg = snapshotsdialog.SnapshotsDialog( self, self.snapshot_id, rel_path)
        if QDialog.Accepted == dlg.exec_():
            if dlg.snapshot_id != self.snapshot_id:
                for index in range( self.list_time_line.topLevelItemCount() ):
                    item = self.list_time_line.topLevelItem( index )
                    snapshot_id = self.time_line_get_snapshot_id( item )
                    if snapshot_id == dlg.snapshot_id:
                        self.snapshot_id = dlg.snapshot_id
                        self.list_time_line.setCurrentItem( item )
                        self.update_files_view( 2 )
                        break

    def on_btn_folder_up_clicked( self ):
        if len( self.path ) <= 1:
            return

        path = os.path.dirname( self.path )
        if self.path == path:
            return

        self.path = path
        self.update_files_view( 0 )

    def on_list_files_view_item_activated( self, model_index ):
        if self.qapp.keyboardModifiers() and Qt.ControlModifier:
            return

        if model_index is None:
            return

        rel_path = str( self.list_files_view_proxy_model.data( model_index ) )
        if not rel_path:
            return

        rel_path = os.path.join( self.path, rel_path )
        full_path = self.snapshots.get_snapshot_path_to( self.snapshot_id, rel_path )

        if os.path.exists( full_path ):
            if self.snapshots.can_open_path( self.snapshot_id, full_path ):
                if os.path.isdir( full_path ):
                    self.path = rel_path
                    self.update_files_view( 0 )
                else:
                    self.run = QDesktopServices.openUrl(QUrl(full_path ))

    def files_view_get_name( self, item ):
        return item.text( 0 )

    def files_view_get_type( self, item ):
        return int( item.text( 4 ) )

    def add_files_view( self, name, size_str, date_str, size_int, type ):
        full_path = self.snapshots.get_snapshot_path_to( self.snapshot_id, os.path.join( self.path, name ) )
        icon = QIcon.fromTheme( QMimeType.iconNameForUrl( QUrl( full_path ) ) )

        item = QTreeWidgetItem( self.list_files_view )

        item.setIcon( 0, icon )
        item.setText( 0, name )
        item.setText( 1, size_str )
        item.setText( 2, date_str )
        item.setText( 3, str( size_int ) )
        item.setText( 4, str( type ) )

        self.list_files_view.addTopLevelItem( item )
        return item

    def update_files_view( self, changed_from, selected_file = None, show_snapshots = False ): #0 - files view change directory, 1 - files view, 2 - time_line, 3 - places
        if 0 == changed_from or 3 == changed_from:
            selected_file = ''

        if 0 == changed_from:
            #update places
            self.list_places.setCurrentItem( None )
            for place_index in range( self.list_places.topLevelItemCount() ):
                item = self.list_places.topLevelItem( place_index )
                if self.path == str( item.data( 0, Qt.UserRole ) ):
                    self.list_places.setCurrentItem( item )
                    break

        tooltip = ''
        text = ''
        if len( self.snapshot_id ) > 1:
            name = self.snapshots.get_snapshot_display_id( self.snapshot_id )
            text = _('Snapshot: %s') % name
            tooltip = _('View the snapshot made at %s') % name
        else:
            tooltip = _('View the current disk content')
            text = _('Now')

        self.right_widget.setTitle( _( text ) )
        self.right_widget.setToolTip( _( tooltip ) )

        #try to keep old selected file
        if selected_file is None:
            selected_file, idx = self.file_selected()

        self.selected_file = selected_file
    
        #update files view
        full_path = self.snapshots.get_snapshot_path_to( self.snapshot_id, self.path )

        if os.path.isdir( full_path ):
            if self.show_hidden_files:
                self.list_files_view_proxy_model.setFilterRegExp(r'')
            else:
                self.list_files_view_proxy_model.setFilterRegExp(r'^[^\.]')

            model_index = self.list_files_view_model.index(full_path)
            proxy_model_index = self.list_files_view_proxy_model.mapFromSource(model_index)
            self.list_files_view.setRootIndex(proxy_model_index)

            self.files_view_toolbar.setEnabled( False )
            self.files_view_layout.setCurrentWidget( self.list_files_view )
            #todo: find a signal for this
            self.on_dir_lister_completed()
        else:
            self.btn_restore_menu.setEnabled( False )
            self.menubar_restore.setEnabled(False)
            self.btn_restore.setEnabled(False)
            self.btn_restore_to.setEnabled(False)
            self.btn_snapshots.setEnabled( False )
            self.files_view_layout.setCurrentWidget( self.lbl_folder_dont_exists )

        #show current path
        self.edit_current_path.setText( self.path )
        self.menu_restore_parent.setText( _("Restore '%s'") % self.path )
        self.menu_restore_parent_to.setText( _("Restore '%s' to ...") % self.path )

        #update folder_up button state
        self.btn_folder_up.setEnabled( len( self.path ) > 1 )

    def on_dir_lister_completed( self ):
        has_files = (self.list_files_view_proxy_model.rowCount(self.list_files_view.rootIndex() ) > 0 )

        #update restore button state
        enable = len(self.snapshot_id) > 1 and has_files
        self.btn_restore_menu.setEnabled(enable)
        self.menubar_restore.setEnabled(enable)
        self.btn_restore.setEnabled(enable)
        self.btn_restore_to.setEnabled(enable)

        #update snapshots button state
        self.btn_snapshots.setEnabled( has_files )

        #enable files toolbar
        self.files_view_toolbar.setEnabled( True )

        #select selected_file
        found = False

        if self.selected_file:
            index = self.list_files_view.indexAt(QPoint(0,0))
            if not index.isValid():
                return
            while index.isValid():
                file_name = (str( self.list_files_view_proxy_model.data(index) ))
                if file_name == self.selected_file:
                    self.list_files_view.setCurrentIndex(index)
                    found = True
                    break
                index = self.list_files_view.indexBelow(index)
            self.selected_file = ''

        if not found and has_files:
            self.list_files_view.setCurrentIndex( self.list_files_view_proxy_model.index( 0, 0 ) )

    def file_selected(self):
        idx = self.list_files_view.currentIndex()
        if idx.column() > 0:
            idx = idx.sibling(idx.row(), 0)
        selected_file = str( self.list_files_view_proxy_model.data( idx ) )
        return(selected_file, idx)

class About(QDialog):
    def __init__(self, parent = None):
        super(About, self).__init__(parent)
        self.parent = parent
        self.config = parent.config
        import icon

        self.setWindowTitle(_('About') + ' ' + self.config.APP_NAME)
        logo     = QLabel('Icon')
        logo.setPixmap(icon.BIT_LOGO.pixmap(QSize(48, 48)) )
        name     = QLabel('<h1>' + self.config.APP_NAME + ' ' + self.config.VERSION + '</h1>')
        name.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        homepage = QLabel(self.mkurl('<http://backintime.le-web.org>'))
        homepage.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        homepage.setOpenExternalLinks(True)
        copyright = QLabel(self.config.COPYRIGHT + '\n')

        vlayout = QVBoxLayout(self)
        hlayout = QHBoxLayout()
        hlayout.addWidget(logo)
        hlayout.addWidget(name)
        hlayout.addStretch()
        vlayout.addLayout(hlayout)
        vlayout.addWidget(homepage)
        vlayout.addWidget(copyright)

        button_box_left  = QDialogButtonBox()
        btn_authors      = button_box_left.addButton(_('Authors'), QDialogButtonBox.ActionRole)
        btn_translations = button_box_left.addButton(_('Translations'), QDialogButtonBox.ActionRole)
        btn_license      = button_box_left.addButton(_('License'), QDialogButtonBox.ActionRole)

        button_box_right = QDialogButtonBox(QDialogButtonBox.Ok)

        hlayout = QHBoxLayout()
        hlayout.addWidget(button_box_left)
        hlayout.addWidget(button_box_right)
        vlayout.addLayout(hlayout)

        QObject.connect(btn_authors, SIGNAL('clicked()'), self.authors)
        QObject.connect(btn_translations, SIGNAL('clicked()'), self.translations)
        QObject.connect(btn_license, SIGNAL('clicked()'), self.license)
        QObject.connect(button_box_right, SIGNAL('accepted()'), self.accept)

    def authors(self):
        return self.show_info(_('Authors'), self.mkurl(self.config.get_authors()) )

    def translations(self):
        return self.show_info(_('Translations'), self.mkurl(self.config.get_translations()) )

    def license(self):
        return self.show_info(_('License'), self.config.get_license())

    def show_info(self, title, msg):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        vlayout = QVBoxLayout(dlg)
        label = QLabel(msg)
        label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        label.setOpenExternalLinks(True)

        scroll_area = QScrollArea()
        scroll_area.setWidget(label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        QObject.connect(button_box, SIGNAL('accepted()'), dlg.accept)

        vlayout.addWidget(scroll_area)
        vlayout.addWidget(button_box)
        return dlg.exec_()

    def mkurl(self, msg):
        msg = re.sub(r'<(.*?)>', self.a_href, msg)
        msg = re.sub(r'\n', '<br>', msg)
        return msg

    def a_href(self, m):
        if m.group(1).count('@'):
            return '<a href="mailto:%(url)s">%(url)s</a>' % {'url': m.group(1)}
        else:
            return '<a href="%(url)s">%(url)s</a>' % {'url': m.group(1)}

def debug_trace():
  '''Set a tracepoint in the Python debugger that works with Qt'''
  from PyQt4.QtCore import pyqtRemoveInputHook
  from pdb import set_trace
  pyqtRemoveInputHook()
  set_trace()

def create_qapplication( cfg ):
    return QApplication(sys.argv + ['-title', cfg.APP_NAME])

if __name__ == '__main__':
    cfg = backintime.start_app( 'backintime-qt4' )

    raise_cmd = ''
    if len( sys.argv ) > 1:
        raise_cmd = '\n'.join( sys.argv[ 1 : ] )

    app_instance = guiapplicationinstance.GUIApplicationInstance( cfg.get_app_instance_file(), raise_cmd )
    cfg.PLUGIN_MANAGER.load_plugins(cfg = cfg)
    cfg.PLUGIN_MANAGER.on_app_start()

    logger.openlog()
    qapp = create_qapplication( cfg )

    main_window = MainWindow( cfg, app_instance, qapp )

    if cfg.is_configured():
        cfg.xWindowId = main_window.winId()
        main_window.show()
        qapp.exec_()

    logger.closelog()

    cfg.PLUGIN_MANAGER.on_app_exit()
    app_instance.exit_application()
