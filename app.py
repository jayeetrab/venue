import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import math
import io
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, func, case
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ============================================================================
# DATABASE SETUP
# ============================================================================

Base = declarative_base()

class Venue(Base):
    __tablename__ = 'venues'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identity
    google_place_id = Column(String, unique=True)
    google_name = Column(String)
    name = Column(String)
    osm_id = Column(Float)
    osm_type = Column(String)
    
    # Type
    amenity = Column(String)
    cuisine = Column(String)
    search_type = Column(String)
    
    # Contact
    google_phone = Column(String)
    google_phone_intl = Column(String)
    phone = Column(String)
    google_website = Column(String)
    website = Column(String)
    
    # Location
    google_vicinity = Column(String)
    address = Column(String)
    housenumber = Column(String)
    postcode = Column(String)
    search_ward = Column(String)
    search_postcode_sector = Column(String)
    search_constituency = Column(String)
    
    # Coordinates
    google_lat = Column(Float)
    google_lng = Column(Float)
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Ratings
    google_rating = Column(Float)
    google_user_ratings_total = Column(Integer)
    google_price_level = Column(Integer)
    
    # Status
    business_status = Column(String)
    validated = Column(Boolean)
    data_source = Column(String)
    is_chain = Column(Boolean)
    
    # Additional
    opening_hours = Column(Text)
    google_opening_hours = Column(Text)
    outdoor_seating = Column(String)
    takeaway = Column(String)
    delivery = Column(String)
    wheelchair = Column(String)
    google_types = Column(Text)
    google_photo_reference = Column(Text)
    
    # Survey fields - THE KEY FEATURES
    visited = Column(Boolean, default=False)
    visit_date = Column(DateTime)
    interest_status = Column(String)  # 'interested', 'not_interested'
    is_priority = Column(Boolean, default=False)
    notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ============================================================================
# DATABASE CLASS
# ============================================================================

class Database:
    def __init__(self):
        self.engine = create_engine('sqlite:///bristol_venues.db', echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def get_all_venues(self):
        return self.session.query(Venue).all()
    
    def get_venue_by_id(self, venue_id):
        return self.session.query(Venue).filter(Venue.id == venue_id).first()
    
    def update_venue(self, venue_id, updates):
        venue = self.get_venue_by_id(venue_id)
        if venue:
            for key, value in updates.items():
                setattr(venue, key, value)
            venue.updated_at = datetime.utcnow()
            self.session.commit()
        return venue
    
    def filter_venues(self, ward=None, postcode_sector=None, amenity=None, 
                      cuisine=None, min_rating=None, visited=None, 
                      interest_status=None, business_status='OPERATIONAL'):
        query = self.session.query(Venue)
        
        if business_status:
            query = query.filter(Venue.business_status == business_status)
        if ward and ward != "All":
            query = query.filter(Venue.search_ward == ward)
        if postcode_sector and postcode_sector != "All":
            query = query.filter(Venue.search_postcode_sector == postcode_sector)
        if amenity and amenity != "All":
            query = query.filter(Venue.amenity == amenity)
        if cuisine and cuisine != "All":
            query = query.filter(Venue.cuisine == cuisine)
        if min_rating and min_rating > 0:
            query = query.filter(Venue.google_rating >= min_rating)
        if visited is not None:
            query = query.filter(Venue.visited == visited)
        if interest_status:
            query = query.filter(Venue.interest_status == interest_status)
        
        return query.all()
    
    def get_statistics(self):
        total = self.session.query(Venue).count()
        visited = self.session.query(Venue).filter(Venue.visited == True).count()
        interested = self.session.query(Venue).filter(Venue.interest_status == 'interested').count()
        not_interested = self.session.query(Venue).filter(Venue.interest_status == 'not_interested').count()
        
        return {
            'total': total,
            'visited': visited,
            'not_visited': total - visited,
            'interested': interested,
            'not_interested': not_interested,
            'conversion_rate': (interested / visited * 100) if visited > 0 else 0
        }
    
    def get_ward_statistics(self):
        results = self.session.query(
            Venue.search_ward,
            func.count(Venue.id).label('total'),
            func.sum(case((Venue.visited == True, 1), else_=0)).label('visited'),
            func.sum(case((Venue.interest_status == 'interested', 1), else_=0)).label('interested'),
            func.sum(case((Venue.interest_status == 'not_interested', 1), else_=0)).label('not_interested')
        ).group_by(Venue.search_ward).order_by(func.count(Venue.id).desc()).all()
        
        return results
    
    def import_from_csv(self, df):
        count = 0
        errors = 0
        
        for _, row in df.iterrows():
            try:
                # Check if venue already exists
                existing = self.session.query(Venue).filter(
                    Venue.google_place_id == row.get('google_place_id')
                ).first()
                
                if existing:
                    continue
                
                venue = Venue(
                    google_place_id=row.get('google_place_id'),
                    google_name=row.get('google_name'),
                    name=row.get('name'),
                    osm_id=float(row.get('osm_id')) if pd.notna(row.get('osm_id')) else None,
                    osm_type=row.get('osm_type'),
                    amenity=row.get('amenity'),
                    cuisine=row.get('cuisine'),
                    search_type=row.get('search_type'),
                    google_phone=row.get('google_phone'),
                    google_phone_intl=row.get('google_phone_intl'),
                    phone=row.get('phone'),
                    google_website=row.get('google_website'),
                    website=row.get('website'),
                    google_vicinity=row.get('google_vicinity'),
                    address=row.get('address'),
                    housenumber=row.get('housenumber'),
                    postcode=row.get('postcode'),
                    search_ward=row.get('search_ward'),
                    search_postcode_sector=row.get('search_postcode_sector'),
                    search_constituency=row.get('search_constituency'),
                    google_lat=float(row.get('google_lat')) if pd.notna(row.get('google_lat')) else None,
                    google_lng=float(row.get('google_lng')) if pd.notna(row.get('google_lng')) else None,
                    latitude=float(row.get('latitude')) if pd.notna(row.get('latitude')) else None,
                    longitude=float(row.get('longitude')) if pd.notna(row.get('longitude')) else None,
                    google_rating=float(row.get('google_rating')) if pd.notna(row.get('google_rating')) else None,
                    google_user_ratings_total=int(row.get('google_user_ratings_total')) if pd.notna(row.get('google_user_ratings_total')) else None,
                    google_price_level=int(row.get('google_price_level')) if pd.notna(row.get('google_price_level')) else None,
                    business_status=row.get('business_status'),
                    validated=bool(row.get('validated')) if pd.notna(row.get('validated')) else False,
                    data_source=row.get('data_source'),
                    is_chain=bool(row.get('is_chain')) if pd.notna(row.get('is_chain')) else False,
                    opening_hours=row.get('opening_hours'),
                    google_opening_hours=row.get('google_opening_hours'),
                    outdoor_seating=row.get('outdoor_seating'),
                    takeaway=row.get('takeaway'),
                    delivery=row.get('delivery'),
                    wheelchair=row.get('wheelchair'),
                    google_types=row.get('google_types'),
                    google_photo_reference=row.get('google_photo_reference')
                )
                
                self.session.add(venue)
                count += 1
                
            except Exception:
                errors += 1
                continue
        
        self.session.commit()
        return count, errors

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles using Haversine formula"""
    if not all([lat1, lon1, lat2, lon2]):
        return None
    
    R = 3959  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 2)

def get_pin_color(venue):
    """Determine pin color based on visit and interest status"""
    if not venue.visited:
        return 'red'  # Not visited
    elif venue.interest_status == 'interested':
        return 'green'  # Hot lead
    elif venue.interest_status == 'not_interested':
        return 'gray'  # Ruled out
    else:
        return 'orange'  # Visited but no status

def create_map_marker(venue, user_lat=None, user_lng=None):
    """Create a Folium marker for a venue"""
    if not venue.google_lat or not venue.google_lng:
        return None
    
    # Calculate distance if user location available
    distance_str = ""
    if user_lat and user_lng:
        dist = calculate_distance(user_lat, user_lng, venue.google_lat, venue.google_lng)
        if dist:
            distance_str = f"<p><b>📏 Distance:</b> {dist} mi from you</p>"
    
    # Status badge
    status_badge = ""
    if venue.visited:
        if venue.interest_status == 'interested':
            status_badge = '<p><b>Status:</b> <span style="color: #10B981; font-weight: bold;">✓ INTERESTED</span></p>'
        elif venue.interest_status == 'not_interested':
            status_badge = '<p><b>Status:</b> <span style="color: #6B7280;">✗ Not Interested</span></p>'
        else:
            status_badge = '<p><b>Status:</b> Visited</p>'
    else:
        status_badge = '<p><b>Status:</b> <span style="color: #EF4444;">Not Visited</span></p>'
    
    # Build popup HTML
    popup_html = f"""
    <div style="width: 280px; font-family: Arial, sans-serif;">
        <h4 style="margin: 0 0 8px 0;">★ {venue.google_rating or 'N/A'} {venue.google_name}</h4>
        <p style="margin: 4px 0; color: #6B7280;"><b>{venue.amenity or 'Venue'}</b>{' • ' + venue.cuisine if venue.cuisine else ''}</p>
        <p style="margin: 4px 0; color: #9CA3AF; font-size: 13px;">{venue.search_ward}, {venue.postcode or 'N/A'}</p>
        <hr style="margin: 8px 0;">
        <p style="margin: 4px 0; font-size: 13px;">📍 {venue.google_vicinity or venue.address or 'N/A'}</p>
        {'<p style="margin: 4px 0; font-size: 13px;">📞 ' + venue.google_phone + '</p>' if venue.google_phone else ''}
        {'<p style="margin: 4px 0; font-size: 13px;">🌐 <a href="' + venue.google_website + '" target="_blank">Website</a></p>' if venue.google_website else ''}
        {status_badge}
        {distance_str}
        {'<p style="margin: 4px 0; font-size: 12px; font-style: italic;">Note: ' + venue.notes + '</p>' if venue.notes else ''}
        <hr style="margin: 8px 0;">
        <a href="https://www.google.com/maps/search/?api=1&query={venue.google_lat},{venue.google_lng}&query_place_id={venue.google_place_id}" target="_blank">
            <button style="width:100%; margin:4px 0; padding:8px; background:#3B82F6; color:white; border:none; border-radius:4px; cursor:pointer; font-size: 13px;">
                🗺️ Open in Google Maps
            </button>
        </a>
        <a href="https://www.google.com/maps/dir/?api=1&destination={venue.google_lat},{venue.google_lng}" target="_blank">
            <button style="width:100%; margin:4px 0; padding:8px; background:#10B981; color:white; border:none; border-radius:4px; cursor:pointer; font-size: 13px;">
                🧭 Get Directions
            </button>
        </a>
    </div>
    """
    
    marker = folium.Marker(
        location=[venue.google_lat, venue.google_lng],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"{venue.google_name} - {venue.amenity}",
        icon=folium.Icon(color=get_pin_color(venue), icon='info-sign')
    )
    
    return marker

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Bristol Venues Survey",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .venue-card {
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        margin-bottom: 1rem;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .stat-card {
        padding: 1.5rem;
        border-radius: 8px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stat-card h2 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: bold;
    }
    .stat-card p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    .badge-interested {
        background: #10B981;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-not-interested {
        background: #6B7280;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
    }
    .badge-not-visited {
        background: #EF4444;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
@st.cache_resource
def get_database():
    return Database()

db = get_database()

# ============================================================================
# SIDEBAR NAVIGATION (with persistent page state)
# ============================================================================

if "page" not in st.session_state:
    st.session_state["page"] = "📊 Dashboard"

def set_page(p):
    st.session_state["page"] = p

st.sidebar.title("🍽️ Bristol Venues Survey")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "🗺️ Map View", "📋 Venue List", "📤 Export", "⚙️ Settings"],
    index=["📊 Dashboard", "🗺️ Map View", "📋 Venue List", "📤 Export", "⚙️ Settings"].index(
        st.session_state["page"]
    ),
    key="nav_radio",
)
st.session_state["page"] = page

st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Stats")
stats = db.get_statistics()
st.sidebar.metric("Total Venues", stats['total'])
st.sidebar.metric("Visited", f"{stats['visited']} ({stats['visited']/stats['total']*100:.1f}%)" if stats['total'] > 0 else "0")
st.sidebar.metric("Hot Leads", stats['interested'])

# ============================================================================
# PAGE: DASHBOARD
# ============================================================================

if st.session_state["page"] == "📊 Dashboard":
    st.title("📊 Survey Dashboard")
    st.markdown("Track your Bristol venue survey progress and TwoTable lead generation")
    
    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
            <h2>{stats['total']}</h2>
            <p>Total Venues</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        visited_pct = (stats['visited']/stats['total']*100) if stats['total'] > 0 else 0
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <h2>{stats['visited']}</h2>
            <p>Visited ({visited_pct:.1f}%)</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <h2>{stats['interested']}</h2>
            <p>Interested Leads</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
            <h2>{stats['conversion_rate']:.1f}%</h2>
            <p>Conversion Rate</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Visit Status Breakdown")
        if stats['total'] > 0:
            status_data = pd.DataFrame({
                'Status': ['Not Visited', 'Visited'],
                'Count': [stats['not_visited'], stats['visited']]
            })
            st.bar_chart(status_data.set_index('Status'), height=300)
        else:
            st.info("No venues in database yet")
    
    with col2:
        st.subheader("🎯 Interest Level (Visited Only)")
        if stats['visited'] > 0:
            interest_data = pd.DataFrame({
                'Interest': ['Interested', 'Not Interested'],
                'Count': [stats['interested'], stats['not_interested']]
            })
            st.bar_chart(
                interest_data.set_index('Interest'),
                height=300,
                color="#10B981",
            )
        else:
            
            st.info("No visited venues yet")
    
    st.markdown("---")
    
    # Ward statistics table
    st.subheader("📍 Coverage by Ward")
    ward_stats = db.get_ward_statistics()
    
    if ward_stats:
        ward_df = pd.DataFrame(ward_stats, columns=['Ward', 'Total', 'Visited', 'Interested', 'Not Interested'])
        ward_df['Completion %'] = (ward_df['Visited'] / ward_df['Total'] * 100).round(1)
        ward_df['Conversion %'] = ((ward_df['Interested'] / ward_df['Visited'] * 100).fillna(0)).round(1)
        
        st.dataframe(
            ward_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ward": st.column_config.TextColumn("Ward", width="medium"),
                "Total": st.column_config.NumberColumn("Total Venues", width="small"),
                "Visited": st.column_config.NumberColumn("Visited", width="small"),
                "Interested": st.column_config.NumberColumn("Interested", width="small"),
                "Not Interested": st.column_config.NumberColumn("Not Interested", width="small"),
                "Completion %": st.column_config.ProgressColumn("Completion", format="%.1f%%", min_value=0, max_value=100),
                "Conversion %": st.column_config.ProgressColumn("Conversion", format="%.1f%%", min_value=0, max_value=100)
            }
        )
    else:
        st.info("No ward data available")
    
    # Quick action buttons
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🟢 View Hot Leads", use_container_width=True):
            st.session_state['quick_filter'] = 'interested'
            set_page("📋 Venue List")
            st.rerun()
    
    with col2:
        if st.button("🔴 View Unvisited", use_container_width=True):
            st.session_state['quick_filter'] = 'not_visited'
            set_page("🗺️ Map View")
            st.rerun()
    
    with col3:
        if st.button("⚪ View Not Interested", use_container_width=True):
            st.session_state['quick_filter'] = 'not_interested'
            set_page("📋 Venue List")
            st.rerun()
    
    with col4:
        if st.button("📊 Export All Data", use_container_width=True):
            set_page("📤 Export")
            st.rerun()

# ============================================================================
# PAGE: MAP VIEW
# ============================================================================

elif st.session_state["page"] == "🗺️ Map View":
    st.title("🗺️ Interactive Map View")
    st.markdown("Explore all Bristol venues on an interactive map")
    
    # Filters in columns
    st.subheader("🔍 Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    all_venues = db.get_all_venues()
    wards = sorted(set(v.search_ward for v in all_venues if v.search_ward))
    postcodes = sorted(set(v.search_postcode_sector for v in all_venues if v.search_postcode_sector))
    amenities = sorted(set(v.amenity for v in all_venues if v.amenity))
    cuisines = sorted(set(v.cuisine for v in all_venues if v.cuisine))
    
    with col1:
        filter_ward = st.selectbox("Ward/Area", ["All"] + wards, key="map_ward")
    
    with col2:
        filter_postcode = st.selectbox("Postcode Sector", ["All"] + postcodes, key="map_postcode")
    
    with col3:
        filter_amenity = st.selectbox("Venue Type", ["All"] + amenities, key="map_amenity")
    
    with col4:
        filter_cuisine = st.selectbox("Cuisine", ["All"] + cuisines, key="map_cuisine")
    
    col5, col6, col7 = st.columns(3)
    
    with col5:
        filter_rating = st.slider("Minimum Rating", 0.0, 5.0, 0.0, 0.5, key="map_rating")
    
    with col6:
        filter_status = st.selectbox(
            "Survey Status",
            ["All", "Not Visited", "Visited", "Interested", "Not Interested"],
            key="map_status"
        )
    
    with col7:
        show_closed = st.checkbox("Show closed venues", value=False, key="map_show_closed")
    
    # Apply filters
    visited_filter = None
    interest_filter = None
    
    if filter_status == "Not Visited":
        visited_filter = False
    elif filter_status == "Visited":
        visited_filter = True
    elif filter_status == "Interested":
        interest_filter = 'interested'
    elif filter_status == "Not Interested":
        interest_filter = 'not_interested'
    
    filtered_venues = db.filter_venues(
        ward=filter_ward,
        postcode_sector=filter_postcode,
        amenity=filter_amenity,
        cuisine=filter_cuisine,
        min_rating=filter_rating,
        visited=visited_filter,
        interest_status=interest_filter,
        business_status=None if show_closed else 'OPERATIONAL'
    )
    
    st.info(f"📍 Showing **{len(filtered_venues)}** venues on map")
    
    # Map legend
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("🔴 **Not Visited**")
    with col2:
        st.markdown("🟢 **Interested**")
    with col3:
        st.markdown("⚪ **Not Interested**")
    with col4:
        st.markdown("🔵 **Your Location**")
    
    # Create map
    bristol_center = [51.4545, -2.5879]
    m = folium.Map(location=bristol_center, zoom_start=13, tiles='OpenStreetMap')
    
    # Add venue markers
    for venue in filtered_venues:
        marker = create_map_marker(venue)
        if marker:
            marker.add_to(m)
    
    # Display map
    st_folium(m, width=None, height=600, key="main_map")
    
    # Statistics below map
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    visited_count = sum(1 for v in filtered_venues if v.visited)
    interested_count = sum(1 for v in filtered_venues if v.interest_status == 'interested')
    not_visited_count = len(filtered_venues) - visited_count
    
    with col1:
        st.metric("Filtered Venues", len(filtered_venues))
    with col2:
        st.metric("Not Visited", not_visited_count)
    with col3:
        st.metric("Visited", visited_count)
    with col4:
        st.metric("Interested", interested_count)

# ============================================================================
# PAGE: VENUE LIST
# ============================================================================

elif st.session_state["page"] == "📋 Venue List":
    st.title("📋 Venue List")
    st.markdown("Browse and manage all venues")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    all_venues = db.get_all_venues()
    wards = sorted(set(v.search_ward for v in all_venues if v.search_ward))
    
    with col1:
        filter_ward = st.selectbox("Filter by Ward", ["All"] + wards, key="list_ward")
    
    with col2:
        filter_status = st.selectbox(
            "Filter by Status", 
            ["All", "Not Visited", "Visited", "Interested", "Not Interested"],
            key="list_status"
        )
    
    with col3:
        search_query = st.text_input("🔍 Search venues", placeholder="Enter venue name...")
    
    # Apply filters
    visited_filter = None
    interest_filter = None
    
    if filter_status == "Not Visited":
        visited_filter = False
    elif filter_status == "Visited":
        visited_filter = True
    elif filter_status == "Interested":
        interest_filter = 'interested'
    elif filter_status == "Not Interested":
        interest_filter = 'not_interested'
    
    venues = db.filter_venues(
        ward=filter_ward if filter_ward != "All" else None,
        visited=visited_filter,
        interest_status=interest_filter
    )
    
    # Apply quick filter from dashboard if present
    quick_filter = st.session_state.get('quick_filter')
    if quick_filter == 'interested':
        venues = [v for v in venues if v.interest_status == 'interested']
    elif quick_filter == 'not_visited':
        venues = [v for v in venues if not v.visited]
    elif quick_filter == 'not_interested':
        venues = [v for v in venues if v.interest_status == 'not_interested']
    # Clear quick_filter after first use
    st.session_state['quick_filter'] = None
    
    # Search filter
    if search_query:
        venues = [v for v in venues if v.google_name and search_query.lower() in v.google_name.lower()]
    
    st.info(f"Showing **{len(venues)}** venues")
    
    # Sort options
    sort_by = st.selectbox("Sort by", ["Name (A-Z)", "Rating (High-Low)", "Visit Date (Recent)"])
    
    if sort_by == "Name (A-Z)":
        venues = sorted(venues, key=lambda x: x.google_name or "")
    elif sort_by == "Rating (High-Low)":
        venues = sorted(venues, key=lambda x: x.google_rating or 0, reverse=True)
    elif sort_by == "Visit Date (Recent)":
        venues = sorted(venues, key=lambda x: x.visit_date or datetime.min, reverse=True)
    
    # Display venues
    for venue in venues:
        with st.expander(f"★ {venue.google_rating or 'N/A'} **{venue.google_name}** - {venue.search_ward}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Basic info
                st.markdown(f"**Type:** {venue.amenity or 'N/A'} {' • ' + venue.cuisine if venue.cuisine else ''}")
                st.markdown(f"**Location:** {venue.search_ward}, {venue.postcode or 'N/A'}")
                st.markdown(f"**Address:** {venue.google_vicinity or venue.address or 'N/A'}")
                
                if venue.google_phone:
                    st.markdown(f"**Phone:** {venue.google_phone}")
                
                if venue.google_website:
                    st.markdown(f"**Website:** [{venue.google_website}]({venue.google_website})")
                
                if venue.google_rating:
                    st.markdown(f"**Rating:** ★ {venue.google_rating}/5.0 ({venue.google_user_ratings_total or 0} reviews)")
                
                # Visit status
                if venue.visited:
                    if venue.interest_status == 'interested':
                        st.markdown('<span class="badge-interested">✓ INTERESTED</span>', unsafe_allow_html=True)
                    elif venue.interest_status == 'not_interested':
                        st.markdown('<span class="badge-not-interested">✗ NOT INTERESTED</span>', unsafe_allow_html=True)
                    else:
                        st.markdown("**Status:** Visited")
                    
                    if venue.visit_date:
                        st.markdown(f"**Visited:** {venue.visit_date.strftime('%b %d, %Y at %I:%M %p')}")
                    
                    if venue.notes:
                        st.markdown(f"**Notes:** _{venue.notes}_")
                else:
                    st.markdown('<span class="badge-not-visited">NOT VISITED</span>', unsafe_allow_html=True)
            
            with col2:
                # Action buttons
                if venue.google_lat and venue.google_lng:
                    st.link_button(
                        "🗺️ Open in Google Maps",
                        f"https://www.google.com/maps/search/?api=1&query={venue.google_lat},{venue.google_lng}&query_place_id={venue.google_place_id}",
                        use_container_width=True
                    )
                    
                    st.link_button(
                        "🧭 Get Directions",
                        f"https://www.google.com/maps/dir/?api=1&destination={venue.google_lat},{venue.google_lng}",
                        use_container_width=True
                    )
                
                if not venue.visited:
                    if st.button("✓ Mark as Visited", key=f"visit_{venue.id}", use_container_width=True):
                        st.session_state[f'marking_visited_{venue.id}'] = True
                        # no immediate rerun; state will be picked up on next rerun
                else:
                    if st.button("📝 Edit Status", key=f"edit_{venue.id}", use_container_width=True):
                        st.session_state[f'editing_{venue.id}'] = True
            
            # Mark as visited modal
            if st.session_state.get(f'marking_visited_{venue.id}', False):
                st.markdown("---")
                st.markdown("### Mark as Visited")
                
                interest_choice = st.radio(
                    "Is this venue interested in TwoTable?",
                    ["Interested", "Not Interested"],
                    key=f"interest_{venue.id}"
                )
                
                notes = st.text_area(
                    "Notes (optional)",
                    placeholder="Manager feedback, observations, follow-up needed, etc.",
                    key=f"notes_{venue.id}"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Cancel", key=f"cancel_{venue.id}", use_container_width=True):
                        st.session_state[f'marking_visited_{venue.id}'] = False
                with col_b:
                    if st.button("💾 Save", key=f"save_{venue.id}", type="primary", use_container_width=True):
                        db.update_venue(venue.id, {
                            'visited': True,
                            'visit_date': datetime.now(),
                            'interest_status': interest_choice.lower().replace(" ", "_"),
                            'notes': notes
                        })
                        st.session_state[f'marking_visited_{venue.id}'] = False
                        st.success(f"✓ {venue.google_name} marked as visited and {interest_choice.lower()}")
                        st.rerun()
            
            # Edit status modal
            if st.session_state.get(f'editing_{venue.id}', False):
                st.markdown("---")
                st.markdown("### Edit Venue Status")
                
                current_idx = 0 if venue.interest_status == 'interested' else 1
                
                new_interest = st.radio(
                    "Change interest status:",
                    ["Interested", "Not Interested"],
                    index=current_idx,
                    key=f"edit_interest_{venue.id}"
                )
                
                new_notes = st.text_area(
                    "Update notes",
                    value=venue.notes or "",
                    key=f"edit_notes_{venue.id}"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Cancel", key=f"edit_cancel_{venue.id}", use_container_width=True):
                        st.session_state[f'editing_{venue.id}'] = False
                with col_b:
                    if st.button("💾 Update", key=f"update_{venue.id}", type="primary", use_container_width=True):
                        db.update_venue(venue.id, {
                            'interest_status': new_interest.lower().replace(" ", "_"),
                            'notes': new_notes
                        })
                        st.session_state[f'editing_{venue.id}'] = False
                        st.success(f"✓ {venue.google_name} updated")
                        st.rerun()

# ============================================================================
# PAGE: EXPORT
# ============================================================================

elif st.session_state["page"] == "📤 Export":
    st.title("📤 Export Data")
    st.markdown("Download venue data in CSV format")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Options")
        
        export_type = st.radio(
            "Select data to export",
            [
                "All Venues",
                "Hot Leads (Interested Only)",
                "Not Interested",
                "Not Visited",
                "Visited (All)",
                "Custom Filter"
            ]
        )
        
        # Get venues based on selection
        if export_type == "All Venues":
            export_venues = db.get_all_venues()
        elif export_type == "Hot Leads (Interested Only)":
            export_venues = db.filter_venues(interest_status='interested')
        elif export_type == "Not Interested":
            export_venues = db.filter_venues(interest_status='not_interested')
        elif export_type == "Not Visited":
            export_venues = db.filter_venues(visited=False)
        elif export_type == "Visited (All)":
            export_venues = db.filter_venues(visited=True)
        else:
            st.markdown("**Custom Filter Options:**")
            all_db_venues = db.get_all_venues()
            custom_ward = st.selectbox("Ward", ["All"] + sorted(set(v.search_ward for v in all_db_venues if v.search_ward)))
            custom_amenity = st.selectbox("Type", ["All"] + sorted(set(v.amenity for v in all_db_venues if v.amenity)))
            
            export_venues = db.filter_venues(
                ward=custom_ward if custom_ward != "All" else None,
                amenity=custom_amenity if custom_amenity != "All" else None
            )
        
        st.metric("Venues to Export", len(export_venues))
    
    with col2:
        st.subheader("Preview")
        
        if export_venues:
            preview_df = pd.DataFrame([{
                'Name': v.google_name,
                'Type': v.amenity,
                'Ward': v.search_ward,
                'Rating': v.google_rating,
                'Visited': '✓' if v.visited else '✗',
                'Interest': v.interest_status.replace('_', ' ').title() if v.interest_status else 'N/A'
            } for v in export_venues[:10]])
            
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
            
            if len(export_venues) > 10:
                st.info(f"Showing first 10 of {len(export_venues)} venues")
    
    st.markdown("---")
    
    # Export button
    if export_venues:
        export_df = pd.DataFrame([{
            'ID': v.id,
            'Name': v.google_name,
            'Type': v.amenity,
            'Cuisine': v.cuisine,
            'Ward': v.search_ward,
            'Postcode': v.postcode,
            'Postcode Sector': v.search_postcode_sector,
            'Address': v.google_vicinity or v.address,
            'Phone': v.google_phone or v.phone,
            'Website': v.google_website or v.website,
            'Rating': v.google_rating,
            'Total Reviews': v.google_user_ratings_total,
            'Price Level': v.google_price_level,
            'Latitude': v.google_lat,
            'Longitude': v.google_lng,
            'Business Status': v.business_status,
            'Visited': v.visited,
            'Visit Date': v.visit_date.strftime('%Y-%m-%d %H:%M:%S') if v.visit_date else None,
            'Interest Status': v.interest_status,
            'Priority': v.is_priority,
            'Notes': v.notes,
            'Data Source': v.data_source
        } for v in export_venues])
        
        csv_buffer = io.StringIO()
        export_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        filename = f"bristol_venues_{export_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )
        
        st.success(f"✓ Ready to download {len(export_venues)} venues")
    else:
        st.warning("No venues match the selected criteria")

# ============================================================================
# PAGE: SETTINGS
# ============================================================================

elif st.session_state["page"] == "⚙️ Settings":
    st.title("⚙️ Settings")
    
    tab1, tab2, tab3 = st.tabs(["📁 Import Data", "🗄️ Database", "ℹ️ About"])
    
    with tab1:
        st.subheader("Import Venues from CSV")
        st.markdown("Upload your **MASTER-FILE.csv** to populate the database")
        
        uploaded_file = st.file_uploader("Choose CSV file", type=['csv'])
        
        if uploaded_file:
            st.info(f"File uploaded: **{uploaded_file.name}** ({uploaded_file.size} bytes)")
            
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✓ CSV loaded successfully: {len(df)} rows, {len(df.columns)} columns")
                
                with st.expander("Preview CSV Data"):
                    st.dataframe(df.head(10), use_container_width=True)
                
                if st.button("🚀 Import to Database", type="primary", use_container_width=True):
                    with st.spinner("Importing venues... This may take a minute."):
                        imported, errors = db.import_from_csv(df)
                    
                    if imported > 0:
                        st.success(f"✓ Successfully imported **{imported}** new venues!")
                    else:
                        st.info("No new venues to import (all already exist)")
                    
                    if errors > 0:
                        st.warning(f"⚠️ {errors} rows had errors and were skipped")
                    
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")
    
    with tab2:
        st.subheader("Database Information")
        
        stats = db.get_statistics()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Venues", stats['total'])
        with col2:
            st.metric("Visited", stats['visited'])
        with col3:
            st.metric("Hot Leads", stats['interested'])
        
        st.markdown("---")
        
        st.warning("⚠️ **Danger Zone**")
        
        with st.expander("Reset Survey Data"):
            st.markdown("This will reset all visit data (visited status, interest status, notes) but **keep all venue records**.")
            
            confirm = st.checkbox("I understand this action cannot be undone")
            
            if confirm:
                if st.button("Reset All Survey Data", type="secondary"):
                    for venue in db.get_all_venues():
                        db.update_venue(venue.id, {
                            'visited': False,
                            'visit_date': None,
                            'interest_status': None,
                            'is_priority': False,
                            'notes': None
                        })
                    st.success("✓ Survey data has been reset")
                    st.rerun()
    
    with tab3:
        st.subheader("About This App")
        
        st.markdown("""
        ### 🍽️ Bristol Venues Field Survey System
        
        **Purpose:** Systematic surveying of 718+ independent restaurants, cafes, pubs, and bars across Bristol for TwoTable partnership lead generation.
        
        **Key Features:**
        - 📊 Dashboard with real-time statistics
        - 🗺️ Interactive map with Leaflet/OpenStreetMap
        - 📋 Comprehensive venue list with filtering
        - ✓ Quick visit marking with interest level capture
        - 📤 Flexible CSV export options
        - 📁 CSV import for venue data
        
        **Technology Stack:**
        - Frontend: Streamlit
        - Database: SQLite
        - Maps: Folium + OpenStreetMap
        - Data: Pandas
        
        **Color Coding:**
        - 🔴 Red = Not visited
        - 🟢 Green = Visited + Interested (hot leads)
        - ⚪ Gray = Visited + Not interested
        
        ---
        
        **Version:** 1.0.0  
        **Created:** February 2026  
        **For:** TwoTable Venue Survey Project
        """)

# ============================================================================
# FOOTER
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("**Bristol Venues Survey v1.0**")
st.sidebar.markdown("Built for TwoTable")
