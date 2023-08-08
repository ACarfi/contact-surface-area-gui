from stl import mesh
import numpy as np
import vtk
import networkx as nx
import multiprocessing

class Mesh3D:
    def __init__(self, path, name):
        self.__name = name
        self.__path = path
        self.__mesh = mesh.Mesh.from_file(self.__path)
        self.__dim = self.__mesh.v0.shape[0]
     
    def mesh_volume(self):
        reader = vtk.vtkSTLReader()
        reader.SetFileName(self.__path)
        reader.Update()
        object = reader.GetOutput()

        # Compute the tumor volume using vtkMassProperties
        mass_properties = vtk.vtkMassProperties()
        mass_properties.SetInputData(object)
        mass_properties.Update()
        return mass_properties.GetVolume()

    #Compute Area of a Specifi Polygon in the Tumor Mesh - Shoelace Formula
    def __polygon_area(self,v0,v1,v2):
        points = np.array([v0,v1,v2])

        #Projection of the three verticies on a plane
        u = points[1]-points[0]
        v = points[2]-points[0]
        
        # n is the vector perpendicular to the plane containing u and v
        n = np.cross(u,v)
        n /= np.sqrt(np.sum(n**2)) # vector normalization

        x = np.array([1,0,0])

        # if n and x are parallel change x
        if (np.cross(x,n)==0).all():
            x = np.array([0,0,1])

        # projection of x onto the plane containing u and v
        x = x - np.dot(x,n)*n
        x /= np.sqrt(np.sum(x**2)) # vector normalization
        y = np.cross(n,x) # y is perpendicular to n and x

        points_p = np.empty([np.shape(points)[1],2])
        for i in range(np.shape(points)[1]):
            points_p[i,0] = np.dot(points[i],x)
            points_p[i,1] = np.dot(points[i],y)

        #Computation of the are with the Shoelace formula
        area = 0

        for i in range(np.shape(points)[1]-1):
            area += points_p[i,0]*points_p[i+1,1]

        for i in range(np.shape(points)[1]-1):
            area -= points_p[i+1,0]*points_p[i,1]

        area += points_p[-1,0]*points_p[0,1]
        area -= points_p[0,0]*points_p[-1,1]
        area = abs(area)/2

        return float(area)
    
    def mesh_area(self, indexes):
        area_tot = 0
        for i in range(0,indexes.shape[0]):
            area_tot += self.__polygon_area(self.__mesh.v0[int(indexes[i])],self.__mesh.v1[int(indexes[i])],self.__mesh.v2[int(indexes[i])])
        return area_tot

    def get_mesh(self):
        return self.__mesh
    
    def get_dim(self):
        return self.__dim
    
    def get_path(self):
        return self.__path
    
    def get_name(self):
        return self.__name

def min_distance(args):
        obj_p, obj_q, i = args
        return np.amin(np.linalg.norm(obj_q-obj_p[i,:],axis=1))

class ContactSurfaceArea:
    def __init__(self, path_O1, name_O1, path_O2, name_O2):

        object1 = Mesh3D(path_O1, name_O1)
        object2 = Mesh3D(path_O2, name_O2)

        if(object1.get_dim() > object2.get_dim()):
            self.__object_p = object2
            self.__object_q = object1
        else:
            self.__object_p = object1
            self.__object_q = object2
        
        self.__soft_threshold = 10
        self.__number_of_disconnected = 0
        self.__csa_area = 0

    def __compute_distance(self, obj_p, obj_q, queue):
        obj_q = (obj_q.v0 + obj_q.v1 + obj_q.v2)/3
        obj_p = (obj_p.v0 + obj_p.v1 + obj_p.v2)/3

        pool = multiprocessing.Pool()
        
        distance = pool.map(min_distance, [(obj_p, obj_q, i) for i in range(0,obj_p.shape[0])])
        return distance

        
    
    def __find_threshold(self,data_to_fit):
        x = np.arange(data_to_fit.shape[0])
        distance = np.empty(data_to_fit.shape[0])
        distance[:] = np.inf

        for i in range(2,data_to_fit.shape[0]-2):
            first = data_to_fit[:i]
            second = data_to_fit[i:-1]
            p1 = np.poly1d(np.polyfit(x[:i],first,1))
            p2 = np.poly1d(np.polyfit(x[i:-1],second,1))

            distance[i] = np.linalg.norm(first-p1(x[:i])) + np.linalg.norm(second-p2(x[i:-1]))
        
        index = np.argmin(distance)       
        return data_to_fit[index]
 
    def compute(self, queue):           
        queue.put("Computing distances!")
        self.__distance = self.__compute_distance(self.__object_p.get_mesh(),self.__object_q.get_mesh(),queue)
        self.__sorted_distance = np.sort(self.__distance)
        
        queue.put("Computing threshold!")
        self.__threshold = self.__find_threshold(self.__sorted_distance[np.where(self.__sorted_distance<self.__soft_threshold)])
        
        queue.put("Computing indexes!")
        self.__csa_indexes = np.where(self.__distance[:]<self.__threshold)[0]
        self.__csa_area = self.__object_p.mesh_area(self.__csa_indexes)

        queue.put("Computing disconnected indexes!")
        self.inspect_mesh(queue)
        if(self.__number_of_disconnected != 0):
            self.complete_csa()

        queue.put(self)
        queue.put("end")

    def display(self):
        reader_obj_q = vtk.vtkSTLReader()
        reader_obj_q.SetFileName(self.__object_q.get_path())    
        reader_obj_q.Update()
        obj_q = reader_obj_q.GetOutput()

        reader_obj_p = vtk.vtkSTLReader()
        reader_obj_p.SetFileName(self.__object_p.get_path())
        reader_obj_p.Update()
        obj_p = reader_obj_p.GetOutput()     

        points = np.empty([obj_p.GetPoints().GetData().GetNumberOfTuples(),3])
        for i in range(0,obj_p.GetPoints().GetData().GetNumberOfTuples()):
            points[i] = np.asarray(obj_p.GetPoints().GetData().GetTuple(i))

        connectivity = np.empty([int(obj_p.GetPolys().GetNumberOfConnectivityIds()/3),3])
        temp = obj_p.GetPolys().GetConnectivityArray()
        for i in range(0,int(obj_p.GetPolys().GetNumberOfConnectivityIds()/3)):
            connectivity[i] = np.array([int(temp.GetComponent(3*i,0)),int(temp.GetComponent(3*i+1,0)),int(temp.GetComponent(3*i+2,0))])
        
        csa_connectvity = connectivity[self.__csa_indexes]

        vtk_points = vtk.vtkPoints()
        for point in points:
            vtk_points.InsertNextPoint(point)

        # Create a vtkCellArray to store the connectivity information
        vtk_cells = vtk.vtkCellArray()
        for cell in csa_connectvity:
            vtk_cells.InsertNextCell(3)  # 3 indicates a triangle cell
            vtk_cells.InsertCellPoint(np.int64(cell[0]))
            vtk_cells.InsertCellPoint(np.int64(cell[1]))
            vtk_cells.InsertCellPoint(np.int64(cell[2]))

        # Create a vtkPolyData object and set the points and cells
        csa = vtk.vtkPolyData()
        csa.SetPoints(vtk_points)
        csa.SetPolys(vtk_cells)

        
        return obj_p, obj_q, csa

    def get_csa(self):
        return self.__csa_area

    def inspect_mesh(self, queue):
        G = nx.Graph()

        vertex_to_face = {}

        for i in range(0,self.__object_p.get_dim()):
            if i not in self.__csa_indexes:
                v0 = tuple(self.__object_p.get_mesh().v0[i])
                v1 = tuple(self.__object_p.get_mesh().v1[i])
                v2 = tuple(self.__object_p.get_mesh().v2[i])
                G.add_edge(v0,v1)
                G.add_edge(v1,v2)
                G.add_edge(v2,v0)

                vertex_to_face[v0] = vertex_to_face.get(v0, []) + [i]
                vertex_to_face[v1] = vertex_to_face.get(v1, []) + [i]
                vertex_to_face[v2] = vertex_to_face.get(v2, []) + [i]
        
        is_connected = nx.is_connected(G)

        if not is_connected:
            # Find the connected components (sub-meshes) of the graph
            sub_meshes = list(nx.connected_components(G))
            sub_mesh_face_ids = []
            for sub_mesh in sub_meshes:
                face_ids = set()
                for vertex in sub_mesh:
                    face_ids.update(vertex_to_face[vertex])
                sub_mesh_face_ids.append(face_ids)
                
            self.__indexes_disconnected = sub_mesh_face_ids
            self.__number_of_disconnected = int(len(sub_meshes))
            self.__disconnected_areas = np.empty(self.__number_of_disconnected)


    def complete_csa(self):
        dist = np.zeros(self.__number_of_disconnected)
        for i,l in enumerate(self.__indexes_disconnected):
            for j,k in enumerate(l):
                if(dist[i]<self.__distance[k]):
                    dist[i] = self.__distance[k]
        
        id_max = np.argmax(dist)

        for i,l in enumerate(self.__indexes_disconnected):
            if(i != id_max):
                for j,k in enumerate(l):
                    self.__csa_indexes = np.append(self.__csa_indexes,k)

    def get_area_obj_p(self):    
        return(self.__object_p.mesh_area(np.arange(self.__object_p.get_dim())))
    
    def get_area_obj_q(self):
        return(self.__object_q.mesh_area(np.arange(self.__object_q.get_dim())))

    def get_volume_obj_p(self):
        return(self.__object_p.mesh_volume())
    
    def get_volume_obj_q(self):
        return(self.__object_q.mesh_volume())
    
    def get_name_obj_p(self):
        return(self.__object_p.get_name())
    
    def get_name_obj_q(self):
        return(self.__object_q.get_name())
    