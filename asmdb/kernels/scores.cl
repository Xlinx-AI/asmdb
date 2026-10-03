__attribute__((reqd_work_group_size(64, 1, 1)))
__kernel void scores(__global const float *matrix,
                     __global const float *query,
                     __global float *output, const ulong rows,
                     const ulong dim) {
    const size_t row = get_group_id(0);
    const size_t lane = get_local_id(0);
    __local float partial[64];
    float sum = 0.0f;
    for (ulong column = lane; column < dim; column += 64)
        sum += matrix[row * dim + column] * query[column];
    partial[lane] = sum;
    barrier(CLK_LOCAL_MEM_FENCE);
    for (uint stride = 32; stride; stride >>= 1) {
        if (lane < stride) partial[lane] += partial[lane + stride];
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    if (lane == 0 && row < rows) output[row] = partial[0];
}
