import sys, vtk, os, multiprocessing
import vtkmodules.vtkRenderingCore as vtkRenderingCore

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QVBoxLayout, QWidget, QPushButton, QLabel, QGridLayout, QSizePolicy
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

from csa import *
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


class ComputationThread(QThread):
    status_updated = pyqtSignal(str)
    computation_finished = pyqtSignal(object)

    def __init__(self, tumor_path, organ_path):
        super().__init__()
        self.tumor_path = tumor_path
        self.organ_path = organ_path

    def run(self):
        csa = ContactSurfaceArea(self.tumor_path, "tumor", self.organ_path, "organ")

        status_queue = multiprocessing.Queue()
        process = multiprocessing.Process(target=csa.compute, args=(status_queue,))


        process.start()       

        while True:
            status_message = status_queue.get()
            if status_message == "end":
                break
            if type(status_message) == str:
                self.status_updated.emit(status_message)
            else:
                self.computation_finished.emit(status_message)

    def run_computation(self, status_queue):
        csa = ContactSurfaceArea(self.tumor_path, "tumor", self.organ_path, "organ")
        csa.compute(status_queue)
        status_queue.put("end")

class FileSelectionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Selection")
        self.setGeometry(100, 100, 400, 200)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.tumor_button = QPushButton("Select Tumor File", self.central_widget)
        self.tumor_button.clicked.connect(self.select_tumor)
        self.layout.addWidget(self.tumor_button)

        self.organ_button = QPushButton("Select Organ File", self.central_widget)
        self.organ_button.clicked.connect(self.select_organ)
        self.layout.addWidget(self.organ_button)

        self.text_box = QLabel(self.central_widget)
        self.layout.addWidget(self.text_box)       

        self.computation_button = QPushButton("Start Computation", self.central_widget)
        self.computation_button.clicked.connect(self.start_computation)
        self.computation_button.setEnabled(False)
        self.layout.addWidget(self.computation_button)

        self.tumor_path = None
        self.organ_path = None

        self.results_window = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_for_messages)

        self.set_app_icon()
       

    def set_app_icon(self):
        icon_dir = os.path.dirname(__file__)
        icon_path = os.path.join(icon_dir, "../resources/logo.png")
        self.setWindowIcon(QIcon(icon_path))

    def select_tumor(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Tumor File", "", "STL Files (*.stl)")
        if file_path:
            self.tumor_path = file_path
            self.tumor_button.setText(f"Tumor File: {file_path}")
            self.check_files_selected()

    def select_organ(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Organ File", "", "STL Files (*.stl)")
        if file_path:
            self.organ_path = file_path
            self.organ_button.setText(f"Organ File: {file_path}")
            self.check_files_selected()

    def check_files_selected(self):
        if self.tumor_path and self.organ_path and self.tumor_path.endswith(".stl") and self.organ_path.endswith(".stl"):
            self.computation_button.setEnabled(True)
        else:
            self.computation_button.setEnabled(False)

    def start_computation(self):
        
        self.tumor_button.setEnabled(False)
        self.organ_button.setEnabled(False)
        self.computation_button.setEnabled(False)

        self.computation_thread = ComputationThread(self.tumor_path, self.organ_path)
        self.computation_thread.status_updated.connect(self.update_status_label)
        self.computation_thread.computation_finished.connect(self.computation_completed)
        self.computation_thread.start()

        self.timer.start(100)
       
    def check_for_messages(self):
        # Process any pending events (including signals from the computation thread)
        app.processEvents()

    def update_status_label(self, status_message):
        self.text_box.setText(status_message)

    def computation_completed(self, csa):
        self.timer.stop()
        self.open_results_window(csa)

    def open_results_window(self, result):
        self.results_window = ResultsWindow(result)
        self.results_window.show()
        self.close()



class ResultsWindow(QMainWindow):
    def __init__(self, csa):
        super().__init__()
        self.setWindowTitle("Results")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.grid_layout = QGridLayout(self.central_widget)
        self.grid_layout.setVerticalSpacing(0)

        self.left_vtk_container = QWidget(self.central_widget)
        self.left_vtk_layout = QVBoxLayout(self.left_vtk_container)

        self.right_vtk_container = QWidget(self.central_widget)
        self.right_vtk_layout = QVBoxLayout(self.right_vtk_container)

        self.text_info_container = QWidget(self.central_widget)  # New widget for text info
        self.text_info_layout = QVBoxLayout(self.text_info_container)
        self.text_info_layout.setSpacing(0)  # Set the spacing between labels (adjust this value as needed)
        self.text_info_layout.setContentsMargins(0, 0, 0, 0)


        self.grid_layout.addWidget(self.left_vtk_container, 0, 0)  # Add left container to grid (row 0, column 0)
        self.grid_layout.addWidget(self.right_vtk_container, 0, 1)  # Add right container to grid (row 0, column 1)
        self.grid_layout.addWidget(self.text_info_container, 0, 2)

        self.vtk_widget1 = QVTKRenderWindowInteractor(self.left_vtk_container)
        self.left_vtk_layout.addWidget(self.vtk_widget1)

        self.vtk_widget2 = QVTKRenderWindowInteractor(self.right_vtk_container)
        self.right_vtk_layout.addWidget(self.vtk_widget2)

        self.set_app_icon()

        # Add QLabel widgets for displaying textual information
        self.add_title_label("Contact Surface Area")
        self.label1 = self.add_info_label(self.text_info_container, str(csa.get_csa()))
        self.label1.setContentsMargins(0, 0, 0, 0)  # Remove margins from label
        self.label1.setAlignment(Qt.AlignCenter)  # Center align the label
        self.text_info_layout.addWidget(self.label1)

        if(csa.get_name_obj_p() == "tumor"):
            area = csa.get_area_obj_p()
            volume = csa.get_volume_obj_p()
        else:
            area = csa.get_area_obj_q()
            volume = csa.get_volume_obj_q()


        self.add_title_label("Tumor Area")
        self.label2 = self.add_info_label(self.text_info_container, str(area))
        self.label2.setAlignment(Qt.AlignCenter)
        self.text_info_layout.addWidget(self.label2)
        
        self.add_title_label("Tumor Volume")
        self.label3 = self.add_info_label(self.text_info_container, str(volume))
        self.label3.setAlignment(Qt.AlignCenter)
        self.text_info_layout.addWidget(self.label3)

        self.text_info_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.label1.setText(str(csa.get_csa()))
        self.label2.setText(str(area))
        self.label3.setText(str(volume))

        obj_p_m, obj_q_m, csa_m = csa.display()
        
        obj_p_mapper = vtkRenderingCore.vtkPolyDataMapper()
        obj_p_mapper.SetInputData(obj_p_m)

        obj_q_mapper = vtkRenderingCore.vtkPolyDataMapper()
        obj_q_mapper.SetInputData(obj_q_m)

        csa_mapper = vtkRenderingCore.vtkPolyDataMapper()
        csa_mapper.SetInputData(csa_m)

        obj_p_actor = vtkRenderingCore.vtkActor()
        obj_p_actor.SetMapper(obj_p_mapper)
        obj_p_actor.GetProperty().SetColor(1.0, 0.0, 0.0)
        obj_p_actor.GetProperty().SetOpacity(1.0)

        obj_q_actor = vtkRenderingCore.vtkActor()
        obj_q_actor.SetMapper(obj_q_mapper)
        obj_q_actor.GetProperty().SetColor(0.0, 1.0, 0.0)
        obj_q_actor.GetProperty().SetOpacity(1.0)

        csa_actor = vtkRenderingCore.vtkActor()
        csa_actor.SetMapper(csa_mapper)
        csa_actor.GetProperty().SetColor(0.0, 0.0, 1.0)
        csa_actor.GetProperty().SetOpacity(1.0)

        renderer1 = vtkRenderingCore.vtkRenderer()
        renderer1.AddActor(obj_p_actor)
        renderer1.AddActor(csa_actor)

        renderer2 = vtkRenderingCore.vtkRenderer()
        renderer2.AddActor(obj_q_actor)
        renderer2.AddActor(csa_actor)

        
        left_render_window =self.vtk_widget1.GetRenderWindow()
        left_render_window.AddRenderer(renderer1)

        right_render_window = self.vtk_widget2.GetRenderWindow()
        right_render_window.AddRenderer(renderer2)

        self.vtk_widget1.SetRenderWindow(left_render_window)
        self.vtk_widget2.SetRenderWindow(right_render_window)

        # Enable interactor
        self.interactor1 = left_render_window.GetInteractor()
        self.interactor1.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.interactor1.Initialize()

        self.interactor2 = right_render_window.GetInteractor()
        self.interactor2.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.interactor2.Initialize()

        # Show the ResultsWindow
        self.showMaximized()

    def set_app_icon(self):
        icon_dir = os.path.dirname(__file__)
        icon_path = os.path.join(icon_dir, "../resources/logo.png")
        self.setWindowIcon(QIcon(icon_path))

    def add_title_label(self, title):
        label = QLabel(title, self.text_info_container)
        label.setAlignment(Qt.AlignCenter)  # Center align the label
        label.setStyleSheet("font-weight: bold;")  # Make the title bold
        self.text_info_layout.addWidget(label)
        return label

    def add_info_label(self, parent, text):
        label = QLabel(text, parent)
        label.setAlignment(Qt.AlignCenter)  # Center align the text
        self.text_info_layout.addWidget(label)
        return label
    
    def closeEvent(self, event):
        # Clean up the VTK renderers and interactors before closing the window
        left_render_window = self.vtk_widget1.GetRenderWindow()
        left_render_window.Finalize()

        right_render_window = self.vtk_widget2.GetRenderWindow()
        right_render_window.Finalize()

        self.interactor1.TerminateApp()
        self.interactor1 = None

        self.interactor2.TerminateApp()
        self.interactor2 = None

        # Call the superclass closeEvent to perform other necessary cleanup
        super().closeEvent(event)
        
if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    file_selection_window = FileSelectionWindow()
    file_selection_window.show()
    sys.exit(app.exec_())

