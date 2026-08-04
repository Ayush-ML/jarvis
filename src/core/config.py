# This Script is responsible for Storing all Hardcoded Values and Configurations for the Jarvis Project
# This is Done to Modularize the Code
# Make it more Readable and Changeable without having to go through the entire codebase or breaking everything
# Importing Necessary Libraries

# None right now

STREAM = True # Whether to Stream the Response or Not
TEMPERATURE = 0.8 # The Temperature of the Model, Higher the Temperature, More Creative or Varied the Response
MAX_TOKENS = 32564
TOOL_CHOICE = 'auto' # Whether the Model uses a Tool or Not, Auto means the Model will Decide on its own, required means it will use a Tool, none means it will not use a Tool
THINKING = True # Whether the Model will Think or Not, Thinking is the Process of the Model Deciding on its own what to do, and how to do it, without any Human Intervention
