# team-06-Next_Mobility_Labs

Project Name: Vehicel 2 Grid physics informed revenue simulator

Team number: 6

Team mates: Daniel Samoylov, Finn Karstens, Lukas Lehmann, Björn Fischer

Challenge: Next Mobility Labs | Vehicle-to-Grid

    Renewable energy has a timing problem. Solar peaks at noon and wind blows at night, but demand peaks in the evening when people come home, cook and plug in their cars. Green power gets wasted when there is a surplus, and fossil plants jump in when it runs short.

    The fix is already parked in every company car park. Electric vehicles are mobile batteries, and they sit unused for an average of 22 hours a day. Vehicle-to-Grid turns them into part of the solution: instead of only consuming energy, they store it when it is green and cheap and feed it back when the grid needs it most.

    The commercial platform that connects fleet operators to the energy system is still white space. How might we build it?

Problem: 
    Fleets of electrical vehicals are a massive unused energy storage capacity.
    Companys hosting fleets like this will be interested in utilizing this unused potential as a revenue sorce.
    The electricity prices are varying by significant margins on the order of hours, and even seconds. The variations on hour timescales are known at least 24 hours in advance and can therefore be used for trading. The grid instability on the order of seconds can not be accurately predicted, but must be compensated for by the grid provider, who is therefore interested in available capacity. This kind of short term decisions about capacity offering and trading can not be made effectively by human employees.
    The commonly known chicken egg problem applies to this case in the form that the highly profitable FCR market is only available to players, that can provide more than 1 MW of storage power. Small fleets of vehicels will not be able to pass that threshold on their own.

Solution:
    We build a system to optimize the former mentioned trading decisions, taking into account real market prices, physical battery degradation and realistic driver logs. 
    Our system is able to perform net profit optimized realtime decisions on charging, discharging and FCR capacity offerings.
    We currently provide a web application, potential customers can use to calculate their lost profit by not being part of our ecosystem.
    Our aim is to build an ecosystem with multiple participating fleets, which form a large aggregator to pass the 1 MW threshold for the FCR participation.

Start the web app: 
    -open two terminals
    -execute in main root/ 

    ```bash
     uvicorn server:app --reload --port 8000 
    ```

    -execute in second terminal in plug-and-earn/ 

    ```bash 
    python -m http.server 5173 
    ```

    -open "localhost:5173/#/" in your browser of choice

    (know that you might need to install dependencies)


