import timeit


code1 = """
def check(x, n): return x if x.count("0") == n / 2 else None;
result_list = [y for x in (f"{i:b}" for i in range(max_bits(n - 1), 2 ** n)) if (y := check(x, n))];
"""
code2 = """
result_list = [y for x in (f"{i:b}" for i in range(max_bits(n - 1), 2 ** n)) if (y := x if x.count("0") == n / 2 else None)]
"""
code3 = """
result_list = [f"{i:b}" for i in range(max_bits(n - 1), 2 ** n) if f"{i:b}".count("0") == n / 2]
"""
code4 = """
generator1 = (f"{i:b}" for i in range(max_bits(n - 1), 2 ** n));
result_list = [x for x in generator1 if x.count("0") == n / 2]
"""

setup = "from main import max_bits; n=10"

print(timeit.timeit(code1, number=10000, setup=setup))
print(timeit.timeit(code2, number=10000, setup=setup))
print(timeit.timeit(code3, number=10000, setup=setup))
print(timeit.timeit(code4, number=10000, setup=setup))
