"""Dataset adapters with explicit provenance and no silent power-flow inference."""


from .opsd_household import (
    OPSDHouseholdChannels,
    OPSD_OOD_HOUSEHOLDS,
    complete_day_blocks as opsd_complete_day_blocks,
    native_net_profile as opsd_native_net_profile,
    replay_profile_2min as opsd_replay_profile_2min,
)
