# Facilities and beamline metadata #

## Facilities

The file `lightsources.org.json` was kindly provided by Danielle
Reeves of [Lighsources.org](http://www.lightsources.org) and Jim Birch
of [Xeno Media](http://www.xenomedia.com/).  In contains the data the
goes into the big table at
[the Light Sources of the World page](http://www.lightsources.org/regions)
as well as the contact information for each facilitiy.

Unfortunately, the contact information in that file is very messy --
inconsistent content and formatting -- so a quick-n-dirty perl script
`munge_json.pl` was written to sanitize the content and rewrite it
into JSON files with entries that look like this:

```json
  "ASRC": {
    "country": "Japan",
    "fullname": "Aichi Synchrotron Radiation Center",
    "active": true,
    "email": "takeda@astf.or.jp",
    "website": "http://www.astf-kha.jp/synchrotron/en/",
    "phone": "+81 0561 76 8331",
    "fax": "+81 0561 21 1652",
    "post": "250-3, Minamiyamaguchi-cho\nSeto\nAichi 489-0965\nJapan"
  }
```

Note that phone and fax number formatting remains inconsistent.

Two files were produced, `synchrotrons.json` contains metadata about
the world's 55 current and past synchrotrons and `fels.json` with
metadata about the world's 18 free-electron lasers.

There is data about other facilties in the file provided by the good
folks at lightsources.org and Xeno Media.  For example, data about
United States Department of Energy nanomaterials user facilities is in
the file.  As those are not places where XAS is measured
(well... OK... one can measure EELS on an electron microscope... but
the [XDI](https://github.com/XraySpectroscopy/XAS-Data-Interchange)
dictionary does not yet have definitions suitable for EELS
mesaurements) those items have been skipped.

Some of our dear, departed facilities have been included by hand in
the sanitizing script, including NSLS-I and DORIS-III.  The reason for
including decommissioned facilities is to capture appropriate metadata
for the large volume of existing data from those facilities.

Note that there are several facilities listed by
[Wikipedia](http://en.wikipedia.org/wiki/List_of_synchrotron_radiation_facilities)
that are not in this listing.

## Beamlines

Bruce wrote a small program, `iucr.pl` to scrape information from the
tables in the IUCr XAFS commission compenium of beamlines in
[the Americas](http://www.iucr.org/resources/commissions/xafs/beamlines-in-the-americas),
[Asia and Oceania](http://www.iucr.org/resources/commissions/xafs/beamlines-in-asia-and-oceania)
and
[Europe](http://www.iucr.org/resources/commissions/xafs/beamlines-in-europe).

This results in three json files, one for each region, with entries
that are grouped by facility and which look like this:

```json
     "BL5S1" : {
         "facility" : "AichiSR",
         "flux" : "10^11",
         "name" : "",
         "purpose" : "General Purpose XAFS",
         "range" : "5 - 20",
         "size" : "0.3x0.5",
         "status" : "Operational",
         "website" : "http://www.astf-kha.jp/synchrotron/en/userguide/gaiyou/bl5s1i_xxafs.html"
	 }
```

The units of energy range are keV.  Unless otherwise stated, the units
on beam size are mm.  The units on photon flux are photons/sec.

## To do

* Need to sync facility nomenclature between `synchrotrons.json` and
  the regional beamline json files.

* Need to snarf alternate names, where possible for beamlines,
  e.g. "Gilda" for ESRF BM8, "GSECARS" for APS 13-BM-D, or the
  additional column for BESSY in the Europe html page.