import logging

def a():
    try:
        1 / 0
    except Exception as e:
        raise ValueError("a 层出错") from e

def b():
    try:
        a()
    except Exception as e:
        raise RuntimeError("b 层出错") from e

def c():
    try:
        b()
    except Exception as e:
        logging.exception("捕获到异常，记录完整异常链：")

if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR, filename='error.log')
    c()