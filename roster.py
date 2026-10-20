"""The 56 playable characters, using canonical art filenames and game texture aliases."""
CHARACTERS = (
    'ami', 'babycoco', 'babycortex', 'babycrash', 'babyntropy', 'babyt', 'bignorm',
    'chick', 'coco', 'cortex', 'crash', 'crate', 'crunch', 'dingodile', 'fakecrash',
    'fixedrillaroo', 'geary', 'gnastygnorc', 'hasty', 'hunter', 'isabella',
    'kingchicken', 'koalakong', 'komodojoe', 'komodomoe', 'krunk', 'labassistant',
    'liz', 'megamix', 'megumi', 'nash', 'nbrio', 'ngin', 'nina', 'nitrusoxide',
    'ntrance', 'ntrophy', 'papupapu', 'pasadena', 'pentapenguin', 'pinstripe',
    'polar', 'pura', 'realvelo', 'rillaroo', 'ripperroo', 'smallnorm', 'spyro',
    'stew', 'tawna', 'tinytiger', 'velo', 'vonclutch', 'yaya', 'zam', 'zem',
)
ALIASES = {'coco_baby': 'babycoco', 'tiny': 'tinytiger', 'nitrosoxide': 'nitrusoxide'}


def character(token):
    token = token.lower()
    # Baby Coco is named coco_baby; check it before the ordinary Coco prefix.
    for prefix in sorted((*CHARACTERS, *ALIASES), key=len, reverse=True):
        if token == prefix or token.startswith(prefix + '_'):
            return ALIASES.get(prefix, prefix)
    raise ValueError('Unknown character portrait: ' + token)
