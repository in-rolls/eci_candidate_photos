from eci_candidate_photos.join import state_key
from eci_candidate_photos.parse import parse_page

PHOTO = "https://results.eci.gov.in/uploads4/candprofile/2024/PC/E24/S01/PUTTA.jpg"
PAGE = """
<h2>Parliamentary Constituency
<span>10 - Eluru <strong> (Andhra Pradesh)</strong></span></h2>
<div class='cand-box'>
  <figure><img src='PHOTO' alt=''></figure>
  <div class='cand-info'>
    <div class='status won'>
      <div style='text-transform: capitalize'>won</div>
      <div>746351 <span>(+ 181857)</span></div>
    </div>
    <div class='nme-prty'><h5>PUTTA MAHESH KUMAR</h5><h6>Telugu Desam</h6></div>
  </div>
</div>
<div class='cand-box'>
  <figure><img src='img/nota.jpg' alt=''></figure>
  <div class='cand-info'>
    <div class='status '><div>lost</div><div>9154 <span>( -737197)</span></div></div>
    <div class='nme-prty'><h5>NOTA</h5><h6>None of the Above</h6></div>
  </div>
</div>
""".replace("PHOTO", PHOTO)


def test_page_gives_seat_candidates_votes_and_photo():
    heading, rows = parse_page(PAGE)
    assert heading == "10 - Eluru (Andhra Pradesh)"
    first, nota = rows
    assert first["candidate"] == "PUTTA MAHESH KUMAR"
    assert first["votes"] == 746351 and first["result"] == "won"
    assert first["photo_url"].endswith("PUTTA.jpg")
    assert nota["nota"] and nota["photo_url"] is None and nota["votes"] == 9154


def test_state_names_from_eci_and_tcpd_agree():
    assert state_key("Jammu and Kashmir") == state_key("Jammu_&_Kashmir")
    assert state_key("NCT OF Delhi") == state_key("Delhi")
    assert state_key("Dadra & Nagar Haveli and Daman & Diu") == state_key(
        "Dadra_&_Nagar_Haveli_&_Daman_&_Diu"
    )


HINDI = """
<h2><span>विधानसभा क्षेत्र भिण्ड (मध्य प्रदेश)</span></h2>
<div class='cand-box'>
  <figure><img src='HINDI_PHOTO'></figure>
  <div class='status won'><div>विजयी</div><div>66420 <span>(+ 14146)</span></div></div>
  <h5>नरेन्द्र सिंह कुशवाह</h5><h6>भारतीय जनता पार्टी</h6>
</div>
""".replace(
    "HINDI_PHOTO",
    "https://results.eci.gov.in/uploads1/candprofile/S12/NAREN-2023-1.jpg",
)


def test_hindi_page_gives_result_votes_and_photo():
    heading, (row,) = parse_page(HINDI)
    assert heading == "विधानसभा क्षेत्र भिण्ड (मध्य प्रदेश)"
    assert row["result"] == "won" and row["votes"] == 66420
    assert row["photo_url"].endswith("NAREN-2023-1.jpg")
