import argparse
from gql import Client, gql, dsl
from gql.transport.requests import RequestsHTTPTransport
import re
import time


def gen_headers():
    try:
        with open('auth.txt', 'r') as auth:
            key = auth.read().strip()
            header = {"Content-Type": "application/json",
                      "Authorization": "Bearer " + key}
            return header
    except FileNotFoundError as e:
        "Could not open auth.txt, please put start.gg api key in auth.txt"


def get_event_id(session, event_slug: str) -> int:
    """
    Get event id from a single event slug
    """
    q = gql("""
    query getEventID($slug: String) {
      event(slug: $slug){
        id
        videogame{
          name
        }
      }
    }
  """)
    params = {"slug": event_slug}

    result = session.execute(q, variable_values=params)

    event_id = result['event']['id']
    game = result['event']['videogame']['name']
    print(event_id)
    return event_id, game


def getEvents(session, tournament_slug: str) -> dict:
    """
    Get a dictionary of event ids and event games from a tournament slug
    """
    q = gql("""
    query getEvents($slug: String) {
    tournament(slug: $slug) {
    events {
      id
      videogame {
        name
      }
    }
    }
    }
    """)

    params = {"slug": tournament_slug}

    event_dict = {}

    result = session.execute(q, variable_values=params)
    for event in result['tournament']['events']:
        event_dict[event['id']] = event['videogame']['name']

    return event_dict


def getAllEventEntrants(event_id: int, inner: dsl.DSLField, ds: dsl.DSLSchema, session, initialPerPage=100):
    """
    Get a complete list of entrants for an event, inner contains the fields you want to get for each entrant
    """
    perPage = initialPerPage

    # startgg has been known to fail from time to time, limits the number of attempts so the program doesn't get stuck
    for i in range(5):
        nodes = []
        # get the number of pages necessary as well as total count of entrants
        query = dsl.dsl_gql(
            dsl.DSLQuery(
                ds.Query.event(id=event_id).select(ds.Event.entrants(query={"page": 1, "perPage": perPage}).select(
                    ds.EntrantConnection.pageInfo.select(ds.PageInfo.total, ds.PageInfo.totalPages)))
            )
        )
        result = session.execute(query)
        total = result['event']['entrants']['pageInfo']['total']
        totalPages = result['event']['entrants']['pageInfo']['totalPages']

        # For each page of entrants, collect each one and collate them into a single list of nodes
        try:
            for page in range(1, totalPages + 1):
                query = dsl.dsl_gql(
                    dsl.DSLQuery(
                        ds.Query.event(id=event_id).select(ds.Event.entrants(query={
                            "page": page, "perPage": perPage}).select(ds.EntrantConnection.nodes.select(*inner)))
                    )
                )
                # probably bad, but retry query until it gets a success.
                # TODO figure out more robust exception handling
                while True:
                    try:
                        result = session.execute(query)
                    except gql.transport.exceptions.TransportServerError as e:
                        time.sleep(4)
                        continue
                    break

                for node in result['event']['entrants']['nodes']:
                    nodes.append(node)

        except Exception as e:
            print(e)
            perPage = perPage / 2

        if len(nodes) == total:
            return nodes

    print("failed to gather entrants")


def getEventPlayers(session, event_id: int, ds: dsl.DSLSchema) -> dict:
    '''
    Get event player information for preview
    '''
    # fields to retrieve for each entrant
    inner = [ds.Entrant.id,
             ds.Entrant.initialSeedNum,
             ds.Entrant.participants.select(
                 ds.Participant.id, ds.Participant.gamerTag, ds.Participant.prefix, ds.Participant.user.select(
                     ds.User.discriminator)
             )]

    # retrieve all entrants from start.gg api
    entrants = getAllEventEntrants(event_id, inner, ds, session, 100)
    players = {}

    # add each player to player dict
    for entrant in entrants:
        seed = entrant['initialSeedNum']
        for participant in entrant['participants']:
            tag = participant['gamerTag']
            prefix = participant['prefix']
            discriminator = participant['user']['discriminator']
            players[discriminator] = {
                'prefix': prefix, 'tag': tag, 'seed': seed}

    return players


def generateEventPreview(player_dict: dict, discriminator_list: list, num_seeds: int) -> None:
    """
    collects top seeds and notable players from dictionary of all of an events players.
    Prints them out to stdout
    """
    # gather top players based on seeding or list of notable players
    top_players = []
    for p in player_dict:
        if p in discriminator_list or player_dict[p]['seed'] <= num_seeds:
            top_players.append(player_dict[p])

    # sort them by seed for printing (not sure if it should work like this)
    top_players = sorted(top_players, key=lambda d: d['seed'])

    # print them all on the same line
    for player in top_players:
        prefix = player['prefix']
        tag = player['tag']
        if prefix:
            print(prefix + "|" + tag, end=',')
        else:
            print(tag, end=",")

    # start a new line for the next game
    print("")


def parseLink(link: str) -> tuple:
    """
    Parses a link from an argument to determine which type of link it is.
    Shortens the link to the tournament/event slug and returns the slug type and value
    """

    # checks if a link contains an event slug. event slugs also contain tournament slugs, so checks first
    # eg. start.gg/tournament/evo-2023/event/guilty-gear-strive
    event_link = re.search(
        "tournament\/[a-zA-Z0-9\-]+\/event\/[a-zA-Z0-9\-]+", link)
    if event_link:
        span = event_link.span()
        return ("event_slug", link[span[0]:span[1]])

    # checks if a link contains a full tournament slug, eg. start.gg/tournament/evo-2023
    tournament_link = re.search("tournament\/[a-zA-Z0-9\-]+", link)
    if tournament_link:
        span = tournament_link.span()
        return ("tournament_full_slug", link[span[0]:span[1]])

    # checks if a link contains a shorthand tournament slug, eg. start.gg/evo
    shorthand_link = re.search("start\.gg\/[a-zA-Z0-9\-]+", link)
    if shorthand_link:
        span = shorthand_link.span()
        return ("shorthand_slug", link[span[0]:span[1]].split('/')[1])

    # if no matches, assume it is a bare tournament shorthand, eg. evo
    return ("shorthand_slug", link)


def parseDiscriminatorList(discriminatorPath: str):
    try:
        with open(discriminatorPath, 'r') as discriminatorFile:
            text = discriminatorFile.read()
            discriminators = text.split("\n")
            return discriminators

    except FileNotFoundError as e:
        print("Discriminator File not found, check path")


def main():

    msg = "Generate Tournament Previews of start.gg events"

    parser = argparse.ArgumentParser(description=msg)
    parser.add_argument(
        "startggLink", help="Link to a start.gg tournament or event")
    parser.add_argument(
        "discriminatorFile", help="File location for a list of player discriminators that ignores seeding", default="", nargs='?')
    parser.add_argument('-n', '--seeds', default=16,
                        help="Number of top seeds to display (default 16)")
    args = parser.parse_args()

    # Select your transport with a defined url endpoint
    transport = RequestsHTTPTransport(url="https://api.start.gg/gql/alpha", headers=gen_headers())

    # Create a GraphQL client using the defined transport
    client = Client(transport=transport, fetch_schema_from_transport=True)

    with client as session:
        assert client.schema is not None
        ds = dsl.DSLSchema(client.schema)

        discriminator_list = parseDiscriminatorList(args.discriminatorFile)
        link_type, link = parseLink(args.startggLink)
        if link_type == "event_slug":
            event_id, game = get_event_id(session, link)
            print(game)
            players = getEventPlayers(session, event_id, ds)
            generateEventPreview(players, discriminator_list, int(args.seeds))
        else:
            event_dict = getEvents(session, link)
            for event in event_dict:
                print(event_dict[event])
                players = getEventPlayers(session, event, ds)
                generateEventPreview(
                    players, discriminator_list, int(args.seeds))


if __name__ == "__main__":
    main()
