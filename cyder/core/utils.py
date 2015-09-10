# Reference http://dev.mysql.com/doc/refman/5.0/en/miscellaneous-functions.html
# TODO, use this on all views touching DNS stuff
def locked_function(lock_name, timeout=10):
    """
    This is a decorator that should be used around any view or function that
    modifies, creates, or deletes a DNS model.
    It's purpose is to prevent this case:

        http://people.mozilla.com/~juber/public/t1_t2_scenario.txt

    """
    def decorator(f):
        def new_function(*args, **kwargs):
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute(
                "SELECT GET_LOCK('{lock_name}', {timeout});".format(
                    lock_name=lock_name, timeout=timeout
                )
            )
            ret = f(*args, **kwargs)
            cursor.execute(
                "SELECT RELEASE_LOCK('{lock_name}');".format(
                    lock_name=lock_name
                )
            )
            return ret
        return new_function
    return decorator
