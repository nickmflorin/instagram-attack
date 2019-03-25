def generate_alterations(passwords):
    altered = []
    # first_level = ['', 'a', '13579', '24680', '09', '1523', '1719', '0609',
    #     '0691', '0991', '36606', '3660664', '6951', '20002']
    first_level = ['123', '1234', '1324', '9887', '']
    second_level = ['!', '!!', '!!!', '@', '`', '!a', '@!', 'a@!']

    for pw in passwords:
        altered.append(pw)
        for alteration in first_level:
            altered.append(pw + alteration)
            for two_alteration in second_level:
                altered.append(pw + alteration + two_alteration)
    return altered
