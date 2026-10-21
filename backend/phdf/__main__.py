import multiprocessing

# First thing: in the built app, a worker process (services/workers.py) starts here too.
multiprocessing.freeze_support()

from phdf.app import main  # noqa: E402

main()
