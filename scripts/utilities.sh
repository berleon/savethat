# module for utility functions / variables.


Color_Off='\033[0m'
Red='\033[0;31m'
Green='\033[0;32m'

function fail {
    echo -e "${Red}FLAKE8 Sanity FAILED!!!$Color_Off"
    exit 1
}


MODULE_NAME="savethat"
