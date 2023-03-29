
min_n = 1000
in_fn = 'camera_matrix.csv'
out_fn = 'coded_camera_matrix.csv'


def code_token(token):
    if not len(token):
        return token
    i = int(token)
    if i == 0:
        return 'n'
    elif i < min_n:
        return 'p'
    return ''


with open(out_fn, 'w') as out_f:
    with open(in_fn, 'r') as in_f:
        # write header line
        out_f.write(in_f.readline())
        l = in_f.readline().strip()
        while l:
            tokens = l.split(',')
            out_f.write(
                tokens[0] + ',' +
                ','.join([code_token(t) for t in tokens[1:]]) + '\n')
            l = in_f.readline().strip()
