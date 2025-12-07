import site
import os

user_site = site.getusersitepackages()
if os.path.isdir(user_site):
    site.addsitedir(user_site)
