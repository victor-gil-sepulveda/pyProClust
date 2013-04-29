'''
Created on 05/02/2013

@author: victor
'''
import os
from pyproclust.clustering.clustering import Clustering
from pyproclust.driver.observer.observable import Observable
from pyproclust.algorithms.dbscan.dbscanAlgorithm import DBSCANAlgorithm
from pyproclust.algorithms.gromos.gromosAlgorithm import GromosAlgorithm
from pyproclust.algorithms.random.RandomAlgorithm import RandomClusteringAlgorithm
from pyproclust.algorithms.kmedoids.kMedoidsAlgorithm import KMedoidsAlgorithm
from pyproclust.algorithms.hierarchical.hierarchicalAlgorithm import HierarchicalClusteringAlgorithm
from pyproclust.algorithms.spectral.spectralClusteringAlgorithm import SpectralClusteringAlgorithm

def run_algorithm(algorithm, algorithm_kwargs, clustering_id, directory):
    """
    This function launches an execution of one clustering algorithm with its parameters. Used mainly to be 
    scheduled.
    
    @param algorithm: Instance of a clustering algorithm.
    
    @param algorithm_kwargs: The parameters needed by the algorithm above to run.
    
    @param clustering_id: An id used to define the resulting clustering.
    
    @param directory: Place where we will store the resulting clusterings.
    """
    clustering = algorithm.perform_clustering(algorithm_kwargs)
    clustering.save_to_disk(directory+"/"+str(clustering_id)+".bin")

class ClusteringExplorator(Observable):

    @classmethod
    def get_available_algorithms(cls):
        """
        This function returns a dictionary that links a clustering algorithm type with its class creator.
        @return: The aforementioned dictionary. 
        """
        return { 
                "spectral": SpectralClusteringAlgorithm,
                "dbscan":  DBSCANAlgorithm,
                "gromos": GromosAlgorithm,
                "kmedoids": KMedoidsAlgorithm,
                "random": RandomClusteringAlgorithm,
                "hierarchical": HierarchicalClusteringAlgorithm
        }
    
    def __init__(self, parameters, matrix_handler, workspace_handler, scheduler, parameters_generator, observer = None):
        """
        Class creator.
        
        @param parameters: Script parameters.
        
        @param matrix_handler: The matrix handler MatrixHandler instance) containing the distance matrix.
        
        @param workspace_handler: The workspace handler containing paths.
        
        @param scheduler: An instance of a Scheduler like object
        
        @param parameters_generator: An instance of AlgorithmRunParametersGenerator, in charge of generating automatically the
        parameters needed for the exploration if those are not givenn.
        
        @param observer: The observer object for this Observable.
        """
        super(ClusteringExplorator,self).__init__(observer)
        
        self.matrix_handler = matrix_handler
        self.workspace_handler = workspace_handler
        self.clustering_parameters = parameters["clustering"]
        self.evaluation_parameters = parameters["evaluation"]
        self.current_clustering_id = 0
        self.parameters_generator = parameters_generator
        self.scheduler = scheduler
    
    @classmethod
    def get_used_algorithms(cls, parameters):
        """
        Extract the algorithm types that have the 'use' flag set to true.
        
        @param parameters: Script parameters.
        
        @return: A list with the used algorithm types.
        """
        names = []
        for algorithm_name in parameters["algorithms"]:
            if parameters["algorithms"][algorithm_name]["use"]:
                names.append(algorithm_name)
        return names
    
    def run(self):
        """
        Executes the whole exploration pipeline:
            - Generates the parameters structures
            - Executes the algorithms for all different parameters
            - Loads the results
            
        @return: A dictionary 'clustering_info' structures indexed by clustering ID. Each of these structures
        contains one generated clustering as well as the algorithm type and parameters used to get it.
        """
        used_algorithms = ClusteringExplorator.get_used_algorithms(self.clustering_parameters)
        
        # Generate all clustering + info structures
        clusterings_info = {}
        for algorithm_type in used_algorithms:
            clusterings_info = dict(clusterings_info.items() + self.schedule_algorithm(algorithm_type).items())
        
        # Wait until all processes have finished
        self.scheduler.consume()
        
        # Load clusterings and put them inside the structure
        clustering_plus_files = Clustering.load_all_from_directory(self.workspace_handler["clusterings"])
        for clustering, filename_with_extension in clustering_plus_files:
            clustering_id = os.path.split(filename_with_extension)[1].split(".")[0]
            clusterings_info[clustering_id]["clustering"] = clustering
        
        return clusterings_info
    
    def schedule_algorithm(self, algorithm_type):
        """
        Structures all the info needed for an algorithm+parameters execution and pushes it into the scheduling queue.
        
        @param algorithm_type: The algorithm type of the clustering algorithm we are working with.
        
        @return: The 'clustering info' structure as defined by  AlgorithmRunParametersGenerator::get_parameters_for_type.
        """
        
        algorithm_data = self.clustering_parameters["algorithms"][algorithm_type]
        
        # The algorithm we are going to use
        algorithm = self.build_algorithm(algorithm_type)
        
        # If not parameters were given we have to get the better ones
        clusterings = []
        
        if algorithm_data["auto"]:
            algorithm_run_params, clusterings =  self.parameters_generator.get_parameters_for_type(algorithm_type)
        else:
            # A list with all the parameters for diverse runs
            algorithm_run_params = algorithm_data["parameters"]
         
        clusterings_info =  self.generate_clustering_info(algorithm_type, algorithm_run_params, clusterings)
        
        # Sometimes getting the best parameters imply getting the clusterings themselves
        if clusterings == []:
            for clustering_id in clusterings_info:
                one_clustering_info = clusterings_info[clustering_id]
                self.scheduler.add_process(clustering_id,
                                          "Generation of clustering with %s algorithm and id %s"%(
                                                                                    one_clustering_info["type"],
                                                                                    clustering_id
                                                                                    ),
                                          run_algorithm,
                                                      {
                                                       "algorithm":algorithm, 
                                                       "clustering_id":clustering_id, 
                                                       "algorithm_kwargs":one_clustering_info["parameters"],
                                                       "directory":self.workspace_handler["clusterings"]
                                                       })
        return clusterings_info
    
    def generate_clustering_info(self, algorithm_type, clustering_parameters, clusterings = []):
        """
        It builds the clustering_info structures by parsing the parameters. 
        
        @param algorithm_type: The algorithm type of the clustering algorithm we are working with.
        
        @param clustering_parameters: The parameters we are going to try with this algorithm.
        
        @param clusterings: In the case that the parameter generation also created the clusterings, this argument
        will hold them. Clustering parameters and clusterings must be correlated so that 'clustering_parameters[i]' where
        the parameters used to get 'clustering[i]'.
        
        @return: A list of clustering_info structures.
        """
        clustering_info = {}
        for i, running_parameters in enumerate(clustering_parameters):
            
            clustering_id = "clustering_%04d"%(self.current_clustering_id)
            self.current_clustering_id += 1
            clustering_info[clustering_id] = {
                                                "type":algorithm_type,
                                                "clustering": None,
                                                "parameters": running_parameters
            }
            
            if clusterings != []:
                clustering_info[clustering_id]["clustering"] = clusterings[i]
        
        return clustering_info
     
    def build_algorithm(self, algorithm_type):
        """
        Creates an algorithm with type 'algorithm_type'.
        
        @param algorithm_type: The algorithm type.
        
        @return: An instance of an algorithm of type 'algorithm_type'.
        """
        distance_matrix = self.matrix_handler.distance_matrix
        algorithm_execution_parameters = {}
        if algorithm_type == "spectral":
            # We need to set number of clusters for performance and to get sigma
            algorithm_execution_parameters["max_clusters"] = self.evaluation_parameters["maximum_clusters"]
            algorithm_execution_parameters["sigma_sq"] = self.clustering_parameters["algorithms"]["spectral"]["sigma"]
        
        if algorithm_type in ["spectral","dbscan","gromos","kmedoids","random","hierarchical"] :
            return ClusteringExplorator.get_available_algorithms()[algorithm_type](distance_matrix, **algorithm_execution_parameters)
        else:
            print "[ERROR][ClusteringExplorator::build_algorithms] Not known algorithm type ( %s )"%(algorithm_type)
            self.notify("SHUTDOWN", "Not known algorithm type ( %s )"%(algorithm_type))
            exit()
    