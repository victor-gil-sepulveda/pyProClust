import time
import numpy.random
import numpy
from pyRMSD.condensedMatrix import CondensedMatrix
# from pyproclust.algorithms.dbscan.dbscanTools import k_dist
from pyproclust.algorithms.dbscan.cython.cythonDbscanTools import k_dist
# import yep

print "Creating data..."
t0 = time.time()
row_size = 5000
matrix_elem_size = row_size*(row_size-1)/2
contents = numpy.random.sample(matrix_elem_size)
matrix = CondensedMatrix(contents)
print "It took",time.time() - t0, "seconds to create the matrix."

# yep.start('file_name.prof')
times = []
buffer = numpy.empty(matrix.row_length)
for i in range (5):
    t0 = time.time()
    k_list = numpy.array(range(5))
    k_dist(k_list, buffer, matrix)
    times.append(time.time() - t0)
times = numpy.array(times)
print "It took %.3f (%.3f) seconds to calculate kdists."%(times.mean(),times.std())
# yep.stop()

# casa
# 7.594 (0.029) -> base version
# 7.667 (0.057) -> without reshaping (using transpose)
# 7.326 (0.067) -> changing mergesort to quicksort
# 7.288 (0.021) -> with both quicksorts

# workstation@bsc
# 9.306 (0.039) -> base
# 9.422 (0.054) -> after list comprehension
# 9.273 (0.014) -> Another list comprehension + use of .T
# 9.038 (0.033) -> Adding buffer (it must be added to outer loop though)
# 8.974 (0.094) -> Adding buffer outside
# 7.102 (0.032) -> Raw Cython
# 2.863 (0.006) -> Cython with buffers and some types
# 2.751 (0.028) -> Cython more optim. and quicksort