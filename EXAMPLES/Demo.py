"""
Demo math model: residential real-estate pricing.

A schema/format demonstration, not a tuned dataset. Every range is a plain
continuous (min, max) pair - no disjoint intervals - so the output space has no
structural blind spots to reason about yet.
"""

from typing import ClassVar

from QBMP.engine import QBMP, rule


class Real_Estate_Pricing_Model(QBMP):

    model: ClassVar[dict] = {
        # Math Model Dependencies
        "Outputs": {
            # Dict of Outputs
            "price_lakhs": {
                # Weightage defining relationship dynamics. Ordered quoins ->
                # mortar; values track each input's leverage on this output
                # (sensitivity x range width), normalised to 100.
                "weights": {
                    "area_sqft": 100,
                    "property_type": 55,
                    "distance_km": 43,
                    "age_years": 20,
                    "floor": 12,
                    "bedrooms": 4
                },
                # Output Range Expected
                "range": (7, 418),
                # Row wise Output Generator
                "engine": "populate_price_lakhs"
            },
            "monthly_rent": {
                "weights": {
                    "area_sqft": 100,
                    "property_type": 55,
                    "distance_km": 43,
                    "age_years": 20,
                    "floor": 12,
                    "bedrooms": 4
                },
                "range": (2880, 167125),
                "engine": "populate_monthly_rent"
            },
            # Depends on four of the six inputs; the weights dict is what
            # declares that, so the engine never sees the other two - and when
            # this output is generated alone they are not columns at all.
            "annual_maintenance": {
                "weights": {
                    "area_sqft": 100,
                    "property_type": 62,
                    "age_years": 40,
                    "floor": 10
                },
                # Declared WIDER than the model can physically produce - the
                # cheapest unit possible is a new 500 sqft Studio at 1,125 and
                # the dearest a 50-year-old 3,500 sqft Villa on floor 20 at
                # 26,460. The bins outside that band can never be filled by any
                # input vector, and the datasheet greys them to say so. Every
                # other output declares exactly what it can reach.
                "range": (500, 28000),
                "engine": "populate_annual_maintenance"
            },
            # A COMBINATIONAL output - declared with "categories" instead of a
            # "range". It cannot drive the sampling hierarchy (there is no span
            # to place landmarks across), so it rides the rows the
            # continuational outputs produce and is reported, never filled.
            "price_band": {
                "weights": {
                    "area_sqft": 100,
                    "property_type": 55,
                    "distance_km": 43,
                    "age_years": 20,
                    "floor": 12,
                    "bedrooms": 4
                },
                "categories": ["Budget", "Mid", "Premium", "Luxury"],
                "engine": "populate_price_band"
            },
            # Banded straight off how far out the plot sits.
            "locality_tier": {
                "weights": {
                    "distance_km": 100
                },
                "categories": ["Prime", "Suburban", "Peripheral"],
                "engine": "populate_locality_tier"
            },
            # Banded off the age of the build.
            "construction_status": {
                "weights": {
                    "age_years": 100
                },
                "categories": ["Under-construction", "Ready-to-move", "Resale"],
                "engine": "populate_construction_status"
            },
            # Newer stock high up tends to be let furnished; old ground-floor
            # stock tends not to be. Two inputs decide it, not one.
            "furnishing": {
                "weights": {
                    "age_years": 60,
                    "floor": 40
                },
                "categories": ["Unfurnished", "Semi-furnished", "Fully-furnished"],
                "engine": "populate_furnishing"
            }
        },
        "Inputs": {
            # Dict of Inputs with Model wide Input Ranges Applicable
            "area_sqft": {
                "range": (500, 3500),
                "default": 1500
            },
            # A COMBINATIONAL input - enumerated rather than swept. There is
            # nothing between "Studio" and "Villa" to interpolate, so every
            # option is visited and the continuous sampling runs inside each.
            "property_type": {
                "categories": ["Studio", "Apartment", "Rowhouse", "Villa"],
                "default": "Apartment"
            },
            "bedrooms": {
                "range": (1, 5),
                "default": 2
            },
            "age_years": {
                "range": (0, 50),
                "default": 10
            },
            "distance_km": {
                "range": (1, 30),
                "default": 10
            },
            "floor": {
                "range": (0, 20),
                "default": 3
            }
        }
    }

    # What each build type does to the headline rate, and to what it costs to
    # keep standing. A villa commands more per sqft and costs more to maintain.
    RATE_BY_TYPE: ClassVar[dict] = {
        "Studio": 0.90,
        "Apartment": 1.00,
        "Rowhouse": 1.10,
        "Villa": 1.25
    }
    UPKEEP_BY_TYPE: ClassVar[dict] = {
        "Studio": 0.90,
        "Apartment": 1.00,
        "Rowhouse": 1.15,
        "Villa": 1.35
    }

    def __init__(self, seed):
        super().__init__(seed)

    # Where one band ends and the next begins. Each table is read in order and
    # the first ceiling the value falls under wins; the last name is the rest.
    BANDS: ClassVar[tuple] = ((80, "Budget"), (180, "Mid"), (300, "Premium"),
                              "Luxury")
    LOCALITY: ClassVar[tuple] = ((6, "Prime"), (15, "Suburban"), "Peripheral")
    STATUS: ClassVar[tuple] = ((1, "Under-construction"),
                               (5, "Ready-to-move"), "Resale")
    FURNISHING: ClassVar[tuple] = ((0.40, "Unfurnished"),
                                   (0.70, "Semi-furnished"), "Fully-furnished")

    @staticmethod
    def _band(value, table):
        """First ceiling the value falls under; the table's last entry is the rest."""
        for ceiling, name in table[:-1]:
            if value < ceiling:
                return name
        return table[-1]

    def _rate_per_sqft(self, bedrooms, age_years, distance_km, floor,
                       property_type):
        """Headline rate a unit commands, before its own area is applied."""
        base = (8000
                - 150 * distance_km    # the city-centre premium decays outward
                - 40 * age_years       # depreciation over the build's life
                + 60 * floor           # higher floors carry a view premium
                + 100 * bedrooms)      # configuration bonus
        return base * self.RATE_BY_TYPE[property_type]

    # rule engines
    @rule('price_lakhs')
    def populate_price_lakhs(self, area_sqft, bedrooms, age_years, distance_km,
                             floor, property_type):

        rate = self._rate_per_sqft(bedrooms, age_years, distance_km, floor,
                                   property_type)
        return round(rate * area_sqft / 1e5, 2)

    @rule('monthly_rent')
    def populate_monthly_rent(self, area_sqft, bedrooms, age_years, distance_km,
                              floor, property_type):

        rate = self._rate_per_sqft(bedrooms, age_years, distance_km, floor,
                                   property_type)
        return round(0.004 * rate * area_sqft, 2)

    @rule('annual_maintenance')
    def populate_annual_maintenance(self, area_sqft, age_years, floor,
                                    property_type):

        upkeep = area_sqft * (2.5 + 0.05 * age_years + 0.03 * floor)
        return round(upkeep * self.UPKEEP_BY_TYPE[property_type], 2)

    @rule('price_band')
    def populate_price_band(self, area_sqft, bedrooms, age_years, distance_km,
                            floor, property_type):

        price = self.populate_price_lakhs(
            area_sqft=area_sqft, bedrooms=bedrooms, age_years=age_years,
            distance_km=distance_km, floor=floor, property_type=property_type)

        return self._band(price, self.BANDS)

    @rule('locality_tier')
    def populate_locality_tier(self, distance_km):

        return self._band(distance_km, self.LOCALITY)

    @rule('construction_status')
    def populate_construction_status(self, age_years):

        return self._band(age_years, self.STATUS)

    @rule('furnishing')
    def populate_furnishing(self, age_years, floor):

        # How ready-to-let the unit reads: newness carries more of it than
        # height does, and both are normalised against their declared ranges.
        readiness = 0.6 * (1 - age_years / 50) + 0.4 * (floor / 20)
        return self._band(readiness, self.FURNISHING)


if __name__ == '__main__':

    data_set = Real_Estate_Pricing_Model(seed=24)

    # Single entrypoint - generates, qualifies, checks coherence, and
    # publishes. `format` picks the writer; `dataset` names a FOLDER, which
    # ends up holding index.html beside dataset_size_10.csv.
    df = data_set.save(
        min_rows=10,  # Scaling
        dataset="dataset_size_10",
        format="csv",
        max_bins=4096,  # Precision - capped by both the 2048 ceiling and by scale
        outputs=[
            'price_lakhs',
            'monthly_rent',
            'annual_maintenance',
            'price_band',
            'locality_tier',
            'construction_status',
            'furnishing'
        ]
    )
    df = data_set.save(
        min_rows=100,  # Scaling
        dataset="dataset_size_100",
        format="xlsx",
        max_bins=1024,  # Precision - under the ceiling; capped by scale alone
        outputs=[
            'price_lakhs',
            'monthly_rent',
            'annual_maintenance',
            'price_band',
            'locality_tier',
            'construction_status',
            'furnishing'
        ]
    )
    df = data_set.save(
        min_rows=1000,  # Scaling
        dataset="dataset_size_1000",
        format="csv",
        max_bins=4096,  # Precision - capped by the 2048 ceiling; scale affords it
        outputs=[
            'price_lakhs',
            'monthly_rent',
            'annual_maintenance',
            'price_band',
            'locality_tier',
            'construction_status',
            'furnishing'
        ]
    )
    df = data_set.save(
        min_rows=10000,  # Scaling
        dataset="dataset_size_10000",
        format="xlsx",
        max_bins=2048,  # Precision - asked for and granted in full
        outputs=[
            'price_lakhs',
            'monthly_rent',
            'annual_maintenance',
            'price_band',
            'locality_tier',
            'construction_status',
            'furnishing'
        ]
    )
