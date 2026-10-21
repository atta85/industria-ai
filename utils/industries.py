"""
Industry dropdown options. Each example is shown as greyed placeholder text
inside the empty problem box, to show users how to describe a problem: what
changed, by how much, since when, and what was already checked.
"""

OTHER = "Other (type your industry)"

INDUSTRIES = {
    "Automotive and auto parts":
        "Example: Paint defects (orange peel) on car body panels rose from 2% to 7% over two weeks after we "
        "changed the paint supplier. Booth temperature and humidity logs look normal.",
    "Aerospace and defense":
        "Example: Ultrasonic inspection is rejecting 6% of machined aluminium brackets for porosity, up from "
        "under 1% last quarter. Same CNC program and material spec.",
    "Cement and building materials":
        "Example: Clinker free lime increased from 1.2% to 2.5% this month and kiln fuel use rose 8%. "
        "Raw mix design was not changed.",
    "Chemicals and petrochemicals":
        "Example: Reactor batch yield dropped from 92% to 84% over the last 10 batches. Feed purity is within "
        "spec, but cooling water temperature has been higher this summer.",
    "Construction and civil infrastructure":
        "Example: Hairline cracks appeared on a newly cast concrete slab within 48 hours of pouring. Curing "
        "was done under hot, windy conditions.",
    "Electronics and semiconductors":
        "Example: Solder joint failures on our PCB assembly line rose to 3% after switching to a new "
        "lead-free paste. Reflow profile unchanged.",
    "Energy and power generation":
        "Example: Boiler efficiency of our 50 MW plant fell from 86% to 81% over two months. Flue gas "
        "temperature has risen by about 25 C.",
    "Fertilizer":
        "Example: Urea prill caking complaints doubled this season. Product moisture is 0.3%, but warehouse "
        "humidity has been high.",
    "Food and beverage":
        "Example: Shelf life of our bottled juice dropped from 9 months to 5 months for the last three "
        "production lots. Pasteurization logs show no deviation.",
    "Glass and ceramics":
        "Example: Bottle breakage at the filling line increased to 1.5% after a furnace rebuild. Wall "
        "thickness checks are within limits.",
    "Logistics and warehousing":
        "Example: Order picking errors rose from 0.5% to 2% after we introduced a new warehouse management "
        "system and changed the rack layout.",
    "Machinery and equipment":
        "Example: Gearbox bearings on our conveyor drives are failing after about 4 months instead of the "
        "rated 2 years. Lubrication schedule is followed.",
    "Metals and steel":
        "Example: Surface cracks on hot-rolled steel billets increased to 4% of output since we switched "
        "scrap suppliers. Casting speed unchanged.",
    "Mining and minerals":
        "Example: Crusher throughput fell 15% over a month while power draw stayed the same. Ore hardness "
        "reports show only small variation.",
    "Oil and gas":
        "Example: Pump seal failures on a crude transfer line rose to one every 3 weeks. Operating pressure "
        "and flow are within design range.",
    "Packaging and printing":
        "Example: Print registration errors on our flexo press rose to 5% of rolls after installing a new "
        "web tension controller.",
    "Paper and pulp":
        "Example: Paper web breaks on machine 2 increased from 2 to 6 per day after changing the pulp blend "
        "to more recycled fibre.",
    "Pharmaceuticals":
        "Example: Tablet hardness is failing on 8% of batches since a new excipient lot. Granule moisture "
        "and compression force are within limits.",
    "Plastics, rubber and polymers":
        "Example: Warpage on injection-molded housings increased from 2% to 11% over three weeks. No change "
        "to the mold or operators was made.",
    "Software, IT and automation":
        "Example: Our production line's SCADA screens became slow after last week's software update. Page "
        "refresh time went from under 1 second to over 5 seconds.",
    "Sugar and distillery":
        "Example: Sugar recovery fell from 10.2% to 9.4% this crushing season. Cane quality reports are "
        "similar to last year.",
    "Textile and apparel":
        "Example: Yarn breakage on ring frames rose from 3 to 9 per hour after a new cotton lot was "
        "introduced last week. Spindle speed and humidity settings are unchanged.",
    "Water and wastewater":
        "Example: Effluent COD from our treatment plant rose from 120 to 260 mg/L in two weeks. Aeration "
        "blowers are running normally.",
    "Biotechnology and life sciences":
        "Example: Fermentation batches give inconsistent yield; some fall 30 to 40% short despite the same "
        "recipe and equipment.",
    "Healthcare equipment and devices":
        "Example: Field returns for our infusion pump motors increased to 2% after a component supplier "
        "change. Bench tests pass.",
    "HVAC and building services":
        "Example: Chiller plant energy use rose 18% this summer while cooling load was similar to last "
        "year. Condenser approach temperature has increased.",
}

GENERIC_EXAMPLE = (
    "Example: Describe what is going wrong, how much it has changed, since when, and what you have "
    "already checked. Numbers help a lot."
)


def industry_options():
    return list(INDUSTRIES.keys()) + [OTHER]


def example_for(industry):
    return INDUSTRIES.get(industry, GENERIC_EXAMPLE)
