
from api.utility import utils
def sendMessage(message:str, code:str="3en", numero:str="+22672484842", crypt:bool=False, iv:str|None=None) -> dict:
    if crypt:
        message = utils.crypt(iv, message)
    data ={"contact": {"urn": f"{numero}"}, 
                "results": {"result": 
						 {"value": f"{code} {message}"
						 }
						}
            } 
    return data