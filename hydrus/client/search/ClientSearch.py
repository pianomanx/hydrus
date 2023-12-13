import collections
import datetime
import re
import threading
import typing

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusSerialisable
from hydrus.core import HydrusTags
from hydrus.core import HydrusText
from hydrus.core import HydrusTime

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientData
from hydrus.client import ClientLocation
from hydrus.client import ClientTime
from hydrus.client.metadata import ClientTags

PREDICATE_TYPE_TAG = 0
PREDICATE_TYPE_NAMESPACE = 1
PREDICATE_TYPE_PARENT = 2
PREDICATE_TYPE_WILDCARD = 3
PREDICATE_TYPE_SYSTEM_EVERYTHING = 4
PREDICATE_TYPE_SYSTEM_INBOX = 5
PREDICATE_TYPE_SYSTEM_ARCHIVE = 6
PREDICATE_TYPE_SYSTEM_UNTAGGED = 7
PREDICATE_TYPE_SYSTEM_NUM_TAGS = 8
PREDICATE_TYPE_SYSTEM_LIMIT = 9
PREDICATE_TYPE_SYSTEM_SIZE = 10
PREDICATE_TYPE_SYSTEM_AGE = 11
PREDICATE_TYPE_SYSTEM_HASH = 12
PREDICATE_TYPE_SYSTEM_WIDTH = 13
PREDICATE_TYPE_SYSTEM_HEIGHT = 14
PREDICATE_TYPE_SYSTEM_RATIO = 15
PREDICATE_TYPE_SYSTEM_DURATION = 16
PREDICATE_TYPE_SYSTEM_MIME = 17
PREDICATE_TYPE_SYSTEM_RATING = 18
PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES = 19
PREDICATE_TYPE_SYSTEM_LOCAL = 20
PREDICATE_TYPE_SYSTEM_NOT_LOCAL = 21
PREDICATE_TYPE_SYSTEM_NUM_WORDS = 22
PREDICATE_TYPE_SYSTEM_FILE_SERVICE = 23
PREDICATE_TYPE_SYSTEM_NUM_PIXELS = 24
PREDICATE_TYPE_SYSTEM_DIMENSIONS = 25
PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_COUNT = 26
PREDICATE_TYPE_SYSTEM_TAG_AS_NUMBER = 27
PREDICATE_TYPE_SYSTEM_KNOWN_URLS = 28
PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS = 29
PREDICATE_TYPE_OR_CONTAINER = 30
PREDICATE_TYPE_LABEL = 31
PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_KING = 32
PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS = 33
PREDICATE_TYPE_SYSTEM_HAS_AUDIO = 34
PREDICATE_TYPE_SYSTEM_MODIFIED_TIME = 35
PREDICATE_TYPE_SYSTEM_FRAMERATE = 36
PREDICATE_TYPE_SYSTEM_NUM_FRAMES = 37
PREDICATE_TYPE_SYSTEM_NUM_NOTES = 38
PREDICATE_TYPE_SYSTEM_NOTES = 39
PREDICATE_TYPE_SYSTEM_HAS_NOTE_NAME = 40
PREDICATE_TYPE_SYSTEM_HAS_ICC_PROFILE = 41
PREDICATE_TYPE_SYSTEM_TIME = 42
PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME = 43
PREDICATE_TYPE_SYSTEM_HAS_HUMAN_READABLE_EMBEDDED_METADATA = 44
PREDICATE_TYPE_SYSTEM_FILE_PROPERTIES = 45
PREDICATE_TYPE_SYSTEM_HAS_EXIF = 46
PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME = 47
PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA = 48
PREDICATE_TYPE_SYSTEM_SIMILAR_TO = 49
PREDICATE_TYPE_SYSTEM_HAS_TRANSPARENCY = 50
PREDICATE_TYPE_SYSTEM_HAS_FORCED_FILETYPE = 51

SYSTEM_PREDICATE_TYPES = {
    PREDICATE_TYPE_SYSTEM_EVERYTHING,
    PREDICATE_TYPE_SYSTEM_INBOX,
    PREDICATE_TYPE_SYSTEM_ARCHIVE,
    PREDICATE_TYPE_SYSTEM_UNTAGGED,
    PREDICATE_TYPE_SYSTEM_NUM_TAGS,
    PREDICATE_TYPE_SYSTEM_LIMIT,
    PREDICATE_TYPE_SYSTEM_SIZE,
    PREDICATE_TYPE_SYSTEM_AGE,
    PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME,
    PREDICATE_TYPE_SYSTEM_MODIFIED_TIME,
    PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME,
    PREDICATE_TYPE_SYSTEM_HASH,
    PREDICATE_TYPE_SYSTEM_WIDTH,
    PREDICATE_TYPE_SYSTEM_HEIGHT,
    PREDICATE_TYPE_SYSTEM_RATIO,
    PREDICATE_TYPE_SYSTEM_DURATION,
    PREDICATE_TYPE_SYSTEM_FRAMERATE,
    PREDICATE_TYPE_SYSTEM_NUM_FRAMES,
    PREDICATE_TYPE_SYSTEM_HAS_AUDIO,
    PREDICATE_TYPE_SYSTEM_FILE_PROPERTIES,
    PREDICATE_TYPE_SYSTEM_HAS_TRANSPARENCY,
    PREDICATE_TYPE_SYSTEM_HAS_EXIF,
    PREDICATE_TYPE_SYSTEM_HAS_HUMAN_READABLE_EMBEDDED_METADATA,
    PREDICATE_TYPE_SYSTEM_HAS_ICC_PROFILE,
    PREDICATE_TYPE_SYSTEM_MIME,
    PREDICATE_TYPE_SYSTEM_RATING,
    PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES,
    PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA,
    PREDICATE_TYPE_SYSTEM_SIMILAR_TO,
    PREDICATE_TYPE_SYSTEM_LOCAL,
    PREDICATE_TYPE_SYSTEM_NOT_LOCAL,
    PREDICATE_TYPE_SYSTEM_NUM_WORDS,
    PREDICATE_TYPE_SYSTEM_NUM_NOTES,
    PREDICATE_TYPE_SYSTEM_HAS_NOTE_NAME,
    PREDICATE_TYPE_SYSTEM_FILE_SERVICE,
    PREDICATE_TYPE_SYSTEM_NUM_PIXELS,
    PREDICATE_TYPE_SYSTEM_DIMENSIONS,
    PREDICATE_TYPE_SYSTEM_NOTES,
    PREDICATE_TYPE_SYSTEM_TAG_AS_NUMBER,
    PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS,
    PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_COUNT,
    PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_KING,
    PREDICATE_TYPE_SYSTEM_KNOWN_URLS,
    PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS,
    PREDICATE_TYPE_SYSTEM_TIME,
    PREDICATE_TYPE_SYSTEM_HAS_FORCED_FILETYPE
}

IGNORED_TAG_SEARCH_CHARACTERS = '[](){}/\\"\'-_'
IGNORED_TAG_SEARCH_CHARACTERS_UNICODE_TRANSLATE = { ord( char ) : ' ' for char in IGNORED_TAG_SEARCH_CHARACTERS }

def CollapseWildcardCharacters( text ):
    
    while '**' in text:
        
        text = text.replace( '**', '*' )
        
    
    return text
    

def ConvertSpecificFiletypesToSummary( specific_mimes: typing.Collection[ int ], only_searchable = True ) -> typing.Collection[ int ]:
    
    specific_mimes_to_process = set( specific_mimes )
    
    summary_mimes = set()
    
    for ( general_mime, mime_group ) in HC.general_mimetypes_to_mime_groups.items():
        
        if only_searchable:
            
            mime_group = set( mime_group )
            mime_group.intersection_update( HC.SEARCHABLE_MIMES )
            
        
        if specific_mimes_to_process.issuperset( mime_group ):
            
            summary_mimes.add( general_mime )
            specific_mimes_to_process.difference_update( mime_group )
            
        
    
    summary_mimes.update( specific_mimes_to_process )
    
    return summary_mimes
    

def ConvertSubtagToSearchable( subtag ):
    
    if subtag == '':
        
        return ''
        
    
    subtag = CollapseWildcardCharacters( subtag )
    
    subtag = subtag.translate( IGNORED_TAG_SEARCH_CHARACTERS_UNICODE_TRANSLATE )
    
    subtag = HydrusText.re_one_or_more_whitespace.sub( ' ', subtag )
    
    subtag = subtag.strip()
    
    return subtag
    

def ConvertSummaryFiletypesToSpecific( summary_mimes: typing.Collection[ int ], only_searchable = True ) -> typing.Collection[ int ]:
    
    specific_mimes = set()
    
    for mime in summary_mimes:
        
        if mime in HC.GENERAL_FILETYPES:
            
            specific_mimes.update( HC.general_mimetypes_to_mime_groups[ mime ] )
            
        else:
            
            specific_mimes.add( mime )
            
        
    
    if only_searchable:
        
        specific_mimes.intersection_update( HC.SEARCHABLE_MIMES )
        
    
    return specific_mimes
    

def ConvertSummaryFiletypesToString( summary_mimes: typing.Collection[ int ] ) -> str:
    
    if set( summary_mimes ) == HC.GENERAL_FILETYPES:
        
        mime_text = 'anything'
        
    else:
        
        summary_mimes = sorted( summary_mimes, key = lambda m: HC.mime_mimetype_string_lookup[ m ] )
        
        mime_text = ', '.join( [ HC.mime_string_lookup[ mime ] for mime in summary_mimes ] )
        
    
    return mime_text
    

def ConvertTagToSearchable( tag ):
    
    ( namespace, subtag ) = HydrusTags.SplitTag( tag )
    
    searchable_subtag = ConvertSubtagToSearchable( subtag )
    
    return HydrusTags.CombineTag( namespace, searchable_subtag )
    

def MergePredicates( predicates ):
    
    master_predicate_dict = {}
    
    for predicate in predicates:
        
        # this works because predicate.__hash__ exists
        
        if predicate in master_predicate_dict:
            
            master_predicate_dict[ predicate ].GetCount().AddCounts( predicate.GetCount() )
            
        else:
            
            master_predicate_dict[ predicate ] = predicate
            
        
    
    return list( master_predicate_dict.values() )
    

def IsComplexWildcard( search_text ):
    
    num_stars = search_text.count( '*' )
    
    if num_stars > 1:
        
        return True
        
    
    if num_stars == 1 and not search_text.endswith( '*' ):
        
        return True
        
    
    return False
    

def SortPredicates( predicates ):
    
    key = lambda p: ( - p.GetCount().GetMinCount(), p.ToString() )
    
    predicates.sort( key = key )
    
    return predicates
    

def SubtagIsEmpty( search_text: str ):
    
    ( namespace, subtag ) = HydrusTags.SplitTag( search_text )
    
    return subtag == ''
    

NUMBER_TEST_OPERATOR_LESS_THAN = 0
NUMBER_TEST_OPERATOR_GREATER_THAN = 1
NUMBER_TEST_OPERATOR_EQUAL = 2
NUMBER_TEST_OPERATOR_APPROXIMATE = 3
NUMBER_TEST_OPERATOR_NOT_EQUAL = 4

number_test_operator_to_str_lookup = {
    NUMBER_TEST_OPERATOR_LESS_THAN : '<',
    NUMBER_TEST_OPERATOR_GREATER_THAN : '>',
    NUMBER_TEST_OPERATOR_EQUAL : '=',
    NUMBER_TEST_OPERATOR_APPROXIMATE : HC.UNICODE_APPROX_EQUAL,
    NUMBER_TEST_OPERATOR_NOT_EQUAL : HC.UNICODE_NOT_EQUAL
}

number_test_str_to_operator_lookup = { value : key for ( key, value ) in number_test_operator_to_str_lookup.items() }

class NumberTest( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_NUMBER_TEST
    SERIALISABLE_NAME = 'Number Test'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, operator = NUMBER_TEST_OPERATOR_EQUAL, value = 1 ):
        
        HydrusSerialisable.SerialisableBase.__init__( self )
        
        self.operator = operator
        self.value = value
        
    
    def __eq__( self, other ):
        
        if isinstance( other, NumberTest ):
            
            return self.__hash__() == other.__hash__()
            
        
        return NotImplemented
        
    
    def __hash__( self ):
        
        return ( self.operator, self.value ).__hash__()
        
    
    def __repr__( self ):
        
        return '{} {}'.format( number_test_operator_to_str_lookup[ self.operator ], self.value )
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self.operator, self.value )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self.operator, self.value ) = serialisable_info
        
    
    def GetLambda( self ):
        
        if self.operator == NUMBER_TEST_OPERATOR_LESS_THAN:
            
            return lambda x: x < self.value
            
        elif self.operator == NUMBER_TEST_OPERATOR_GREATER_THAN:
            
            return lambda x: x > self.value
            
        elif self.operator == NUMBER_TEST_OPERATOR_EQUAL:
            
            return lambda x: x == self.value
            
        elif self.operator == NUMBER_TEST_OPERATOR_APPROXIMATE:
            
            lower = self.value * 0.85
            upper = self.value * 1.15
            
            return lambda x: lower < x < upper
            
        
    
    def IsAnythingButZero( self ):
        
        return self.operator == NUMBER_TEST_OPERATOR_GREATER_THAN and self.value == 0
        
    
    def IsZero( self ):
        
        actually_zero = self.operator == NUMBER_TEST_OPERATOR_EQUAL and self.value == 0
        less_than_one = self.operator == NUMBER_TEST_OPERATOR_LESS_THAN and self.value == 1
        
        return actually_zero or less_than_one
        
    
    def WantsZero( self ):
        
        return self.GetLambda()( 0 )
        
    
    @staticmethod
    def STATICCreateFromCharacters( operator_str: str, value: int ) -> "NumberTest":
        
        operator = number_test_str_to_operator_lookup[ operator_str ]
        
        return NumberTest( operator, value )
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_NUMBER_TEST ] = NumberTest

class FileSystemPredicates( object ):
    
    def __init__( self, system_predicates: typing.Collection[ "Predicate" ] ):
        
        self._has_system_everything = False
        
        self._inbox = False
        self._archive = False
        self._local = False
        self._not_local = False
        
        self._common_info = {}
        self._timestamp_ranges = collections.defaultdict( dict )
        
        self._limit = None
        self._similar_to_files = None
        self._similar_to_data = None
        
        self._required_file_service_statuses = collections.defaultdict( set )
        self._excluded_file_service_statuses = collections.defaultdict( set )
        
        self._ratings_predicates = []
        
        self._num_tags_predicates = []
        
        self._duplicate_count_predicates = []
        
        self._king_filter = None
        
        self._file_viewing_stats_predicates = []
        
        new_options = HG.client_controller.new_options
        
        for predicate in system_predicates:
            
            predicate_type = predicate.GetType()
            value = predicate.GetValue()
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_EVERYTHING: self._has_system_everything = True
            if predicate_type == PREDICATE_TYPE_SYSTEM_INBOX: self._inbox = True
            if predicate_type == PREDICATE_TYPE_SYSTEM_ARCHIVE: self._archive = True
            if predicate_type == PREDICATE_TYPE_SYSTEM_LOCAL: self._local = True
            if predicate_type == PREDICATE_TYPE_SYSTEM_NOT_LOCAL: self._not_local = True
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_KNOWN_URLS:
                
                ( operator, rule_type, rule, description ) = value
                
                if 'known_url_rules' not in self._common_info:
                    
                    self._common_info[ 'known_url_rules' ] = []
                    
                
                self._common_info[ 'known_url_rules' ].append( ( operator, rule_type, rule ) )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_AUDIO:
                
                has_audio = value
                
                self._common_info[ 'has_audio' ] = has_audio
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_TRANSPARENCY:
                
                has_transparency = value
                
                self._common_info[ 'has_transparency' ] = has_transparency
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_EXIF:
                
                has_exif = value
                
                self._common_info[ 'has_exif' ] = has_exif
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_HUMAN_READABLE_EMBEDDED_METADATA:
                
                has_human_readable_embedded_metadata = value
                
                self._common_info[ 'has_human_readable_embedded_metadata' ] = has_human_readable_embedded_metadata
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_ICC_PROFILE:
                
                has_icc_profile = value
                
                self._common_info[ 'has_icc_profile' ] = has_icc_profile
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_FORCED_FILETYPE:
                
                has_forced_filetype = value
                
                self._common_info[ 'has_forced_filetype' ] = has_forced_filetype
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HASH:
                
                ( hashes, hash_type ) = value
                
                self._common_info[ 'hash' ] = ( hashes, hash_type, predicate.IsInclusive() )
                
            
            if predicate_type in ( PREDICATE_TYPE_SYSTEM_AGE, PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME, PREDICATE_TYPE_SYSTEM_MODIFIED_TIME, PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME ):
                
                ( operator, age_type, age_value ) = value
                
                if age_type == 'delta':
                    
                    ( years, months, days, hours ) = age_value
                    
                    dt = HydrusTime.CalendarDeltaToDateTime( years, months, days, hours )
                    
                    time_pivot = HydrusTime.DateTimeToTimestamp( dt )
                    
                    # this is backwards (less than means min timestamp) because we are talking about age, not timestamp
                    
                    # the before/since semantic logic is:
                    # '<' 7 days age means 'since that date'
                    # '>' 7 days ago means 'before that date'
                    
                    if operator == '<':
                        
                        self._timestamp_ranges[ predicate_type ][ '>' ] = time_pivot
                        
                    elif operator == '>':
                        
                        self._timestamp_ranges[ predicate_type ][ '<' ] = time_pivot
                        
                    elif operator == HC.UNICODE_APPROX_EQUAL:
                        
                        rough_timedelta_gap = HydrusTime.CalendarDeltaToRoughDateTimeTimeDelta( years, months, days, hours ) * 0.15
                        
                        earliest_dt = dt - rough_timedelta_gap
                        latest_dt = dt + rough_timedelta_gap
                        
                        earliest_time_pivot = HydrusTime.DateTimeToTimestamp( earliest_dt )
                        latest_time_pivot = HydrusTime.DateTimeToTimestamp( latest_dt )
                        
                        self._timestamp_ranges[ predicate_type ][ '>' ] = earliest_time_pivot
                        self._timestamp_ranges[ predicate_type ][ '<' ] = latest_time_pivot
                        
                    
                elif age_type == 'date':
                    
                    ( year, month, day, hour, minute ) = age_value
                    
                    dt = HydrusTime.GetDateTime( year, month, day, hour, minute )
                    
                    time_pivot = HydrusTime.DateTimeToTimestamp( dt )
                    
                    dt_day_of_start = HydrusTime.GetDateTime( year, month, day, 0, 0 )
                    
                    day_of_start = HydrusTime.DateTimeToTimestamp( dt_day_of_start )
                    day_of_end = HydrusTime.DateTimeToTimestamp( ClientTime.CalendarDelta( dt_day_of_start, day_delta = 1 ) )
                    
                    # the before/since semantic logic is:
                    # '<' 2022-05-05 means 'before that date'
                    # '>' 2022-05-05 means 'since that date'
                    
                    if operator == '<':
                        
                        self._timestamp_ranges[ predicate_type ][ '<' ] = time_pivot
                        
                    elif operator == '>':
                        
                        self._timestamp_ranges[ predicate_type ][ '>' ] = time_pivot
                        
                    elif operator == '=':
                        
                        self._timestamp_ranges[ predicate_type ][ '>' ] = day_of_start
                        self._timestamp_ranges[ predicate_type ][ '<' ] = day_of_end
                        
                    elif operator == HC.UNICODE_APPROX_EQUAL:
                        
                        previous_month_timestamp = HydrusTime.DateTimeToTimestamp( ClientTime.CalendarDelta( dt, month_delta = -1 ) )
                        next_month_timestamp = HydrusTime.DateTimeToTimestamp( ClientTime.CalendarDelta( dt, month_delta = 1 ) )
                        
                        self._timestamp_ranges[ predicate_type ][ '>' ] = previous_month_timestamp
                        self._timestamp_ranges[ predicate_type ][ '<' ] = next_month_timestamp
                        
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_MIME:
                
                summary_mimes = value
                
                if isinstance( summary_mimes, int ):
                    
                    summary_mimes = ( summary_mimes, )
                    
                
                self._common_info[ 'mimes' ] = ConvertSummaryFiletypesToSpecific( summary_mimes )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_DURATION:
                
                ( operator, duration ) = value
                
                if operator == '<': self._common_info[ 'max_duration' ] = duration
                elif operator == '>': self._common_info[ 'min_duration' ] = duration
                elif operator == '=': self._common_info[ 'duration' ] = duration
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_duration' ] = duration
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    if duration == 0:
                        
                        self._common_info[ 'duration' ] = 0
                        
                    else:
                        
                        self._common_info[ 'min_duration' ] = int( duration * 0.85 )
                        self._common_info[ 'max_duration' ] = int( duration * 1.15 )
                        
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_FRAMERATE:
                
                ( operator, framerate ) = value
                
                if operator == '<': self._common_info[ 'max_framerate' ] = framerate
                elif operator == '>': self._common_info[ 'min_framerate' ] = framerate
                elif operator == '=': self._common_info[ 'framerate' ] = framerate
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_framerate' ] = framerate
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_NUM_FRAMES:
                
                ( operator, num_frames ) = value
                
                if operator == '<': self._common_info[ 'max_num_frames' ] = num_frames
                elif operator == '>': self._common_info[ 'min_num_frames' ] = num_frames
                elif operator == '=': self._common_info[ 'num_frames' ] = num_frames
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_num_frames' ] = num_frames
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    if num_frames == 0:
                        
                        self._common_info[ 'num_frames' ] = 0
                        
                    else:
                        
                        self._common_info[ 'min_num_frames' ] = int( num_frames * 0.85 )
                        self._common_info[ 'max_num_frames' ] = int( num_frames * 1.15 )
                        
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_RATING:
                
                ( operator, value, service_key ) = value
                
                self._ratings_predicates.append( ( operator, value, service_key ) )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_RATIO:
                
                ( operator, ratio_width, ratio_height ) = value
                
                if operator == '=': self._common_info[ 'ratio' ] = ( ratio_width, ratio_height )
                elif operator == 'wider than':
                    
                    self._common_info[ 'min_ratio' ] = ( ratio_width, ratio_height )
                    
                elif operator == 'taller than':
                    
                    self._common_info[ 'max_ratio' ] = ( ratio_width, ratio_height )
                    
                elif operator == HC.UNICODE_NOT_EQUAL:
                    
                    self._common_info[ 'not_ratio' ] = ( ratio_width, ratio_height )
                    
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    self._common_info[ 'min_ratio' ] = ( ratio_width * 0.85, ratio_height )
                    self._common_info[ 'max_ratio' ] = ( ratio_width * 1.15, ratio_height )
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_SIZE:
                
                ( operator, size, unit ) = value
                
                size = size * unit
                
                if operator == '<': self._common_info[ 'max_size' ] = size
                elif operator == '>': self._common_info[ 'min_size' ] = size
                elif operator == '=': self._common_info[ 'size' ] = size
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_size' ] = size
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    self._common_info[ 'min_size' ] = int( size * 0.85 )
                    self._common_info[ 'max_size' ] = int( size * 1.15 )
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_NUM_TAGS:
                
                self._num_tags_predicates.append( predicate.Duplicate() )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_TAG_AS_NUMBER:
                
                ( namespace, operator, num ) = value
                
                if operator == '<': self._common_info[ 'max_tag_as_number' ] = ( namespace, num )
                elif operator == '>': self._common_info[ 'min_tag_as_number' ] = ( namespace, num )
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    self._common_info[ 'min_tag_as_number' ] = ( namespace, int( num * 0.85 ) )
                    self._common_info[ 'max_tag_as_number' ] = ( namespace, int( num * 1.15 ) )
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_WIDTH:
                
                ( operator, width ) = value
                
                if operator == '<': self._common_info[ 'max_width' ] = width
                elif operator == '>': self._common_info[ 'min_width' ] = width
                elif operator == '=': self._common_info[ 'width' ] = width
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_width' ] = width
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    if width == 0: self._common_info[ 'width' ] = 0
                    else:
                        
                        self._common_info[ 'min_width' ] = int( width * 0.85 )
                        self._common_info[ 'max_width' ] = int( width * 1.15 )
                        
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_NUM_PIXELS:
                
                ( operator, num_pixels, unit ) = value
                
                num_pixels = num_pixels * unit
                
                if operator == '<': self._common_info[ 'max_num_pixels' ] = num_pixels
                elif operator == '>': self._common_info[ 'min_num_pixels' ] = num_pixels
                elif operator == '=': self._common_info[ 'num_pixels' ] = num_pixels
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_num_pixels' ] = num_pixels
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    self._common_info[ 'min_num_pixels' ] = int( num_pixels * 0.85 )
                    self._common_info[ 'max_num_pixels' ] = int( num_pixels * 1.15 )
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HEIGHT:
                
                ( operator, height ) = value
                
                if operator == '<': self._common_info[ 'max_height' ] = height
                elif operator == '>': self._common_info[ 'min_height' ] = height
                elif operator == '=': self._common_info[ 'height' ] = height
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_height' ] = height
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    if height == 0:
                        
                        self._common_info[ 'height' ] = 0
                        
                    else:
                        
                        self._common_info[ 'min_height' ] = int( height * 0.85 )
                        self._common_info[ 'max_height' ] = int( height * 1.15 )
                        
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_NUM_NOTES:
                
                ( operator, num_notes ) = value
                
                if operator == '<': self._common_info[ 'max_num_notes' ] = num_notes
                elif operator == '>': self._common_info[ 'min_num_notes' ] = num_notes
                elif operator == '=': self._common_info[ 'num_notes' ] = num_notes
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_HAS_NOTE_NAME:
                
                ( operator, name ) = value
                
                if operator:
                    
                    label = 'has_note_names'
                    
                else:
                    
                    label = 'not_has_note_names'
                    
                
                if label not in self._common_info:
                    
                    self._common_info[ label ] = set()
                    
                
                self._common_info[ label ].add( name )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_NUM_WORDS:
                
                ( operator, num_words ) = value
                
                if operator == '<': self._common_info[ 'max_num_words' ] = num_words
                elif operator == '>': self._common_info[ 'min_num_words' ] = num_words
                elif operator == '=': self._common_info[ 'num_words' ] = num_words
                elif operator == HC.UNICODE_NOT_EQUAL: self._common_info[ 'not_num_words' ] = num_words
                elif operator == HC.UNICODE_APPROX_EQUAL:
                    
                    if num_words == 0: self._common_info[ 'num_words' ] = 0
                    else:
                        
                        self._common_info[ 'min_num_words' ] = int( num_words * 0.85 )
                        self._common_info[ 'max_num_words' ] = int( num_words * 1.15 )
                        
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_LIMIT:
                
                limit = value
                
                if self._limit is None:
                    
                    self._limit = limit
                    
                else:
                    
                    self._limit = min( limit, self._limit )
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_FILE_SERVICE:
                
                ( operator, status, service_key ) = value
                
                if operator:
                    
                    self._required_file_service_statuses[ service_key ].add( status )
                    
                else:
                    
                    self._excluded_file_service_statuses[ service_key ].add( status )
                    
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES:
                
                ( hashes, max_hamming ) = value
                
                self._similar_to_files = ( hashes, max_hamming )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA:
                
                ( pixel_hashes, perceptual_hashes, max_hamming ) = value
                
                self._similar_to_data = ( pixel_hashes, perceptual_hashes, max_hamming )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_COUNT:
                
                ( operator, num_relationships, dupe_type ) = value
                
                self._duplicate_count_predicates.append( ( operator, num_relationships, dupe_type ) )
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_KING:
                
                king = value
                
                self._king_filter = king
                
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS:
                
                ( view_type, viewing_locations, operator, viewing_value ) = value
                
                self._file_viewing_stats_predicates.append( ( view_type, viewing_locations, operator, viewing_value ) )
                
            
        
    
    def GetDuplicateRelationshipCountPredicates( self ):
        
        return self._duplicate_count_predicates
        
    
    def GetFileServiceStatuses( self ):
        
        return ( self._required_file_service_statuses, self._excluded_file_service_statuses )
        
    
    def GetFileViewingStatsPredicates( self ):
        
        return self._file_viewing_stats_predicates
        
    
    def GetKingFilter( self ):
        
        return self._king_filter
        
    
    def GetLimit( self, apply_implicit_limit = True ):
        
        if self._limit is None and apply_implicit_limit:
            
            forced_search_limit = HG.client_controller.new_options.GetNoneableInteger( 'forced_search_limit' )
            
            return forced_search_limit
            
        
        return self._limit
        
    
    def GetNumTagsNumberTests( self ) -> typing.Dict[ str, typing.List[ NumberTest ] ]:
        
        namespaces_to_tests = collections.defaultdict( list )
        
        for predicate in self._num_tags_predicates:
            
            ( namespace, operator, value ) = predicate.GetValue()
            
            test = NumberTest.STATICCreateFromCharacters( operator, value )
            
            namespaces_to_tests[ namespace ].append( test )
            
        
        return namespaces_to_tests
        
    
    def GetRatingsPredicates( self ):
        
        return self._ratings_predicates
        
    
    def GetSimilarToData( self ):
        
        return self._similar_to_data
        
    
    def GetSimilarToFiles( self ):
        
        return self._similar_to_files
        
    
    def GetSimpleInfo( self ):
        
        return self._common_info
        
    
    def GetTimestampRanges( self ):
        
        return self._timestamp_ranges
        
    
    def HasSimilarToData( self ):
        
        return self._similar_to_data is not None
        
    
    def HasSimilarToFiles( self ):
        
        return self._similar_to_files is not None
        
    
    def HasSystemEverything( self ):
        
        return self._has_system_everything
        
    
    def HasSystemLimit( self ):
        
        return self._limit is not None
        
    
    def MustBeArchive( self ): return self._archive
    
    def MustBeInbox( self ): return self._inbox
    
    def MustBeLocal( self ): return self._local
    
    def MustNotBeLocal( self ): return self._not_local
    
SEARCH_TYPE_AND = 0
SEARCH_TYPE_OR = 1

class FileSearchContext( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_FILE_SEARCH_CONTEXT
    SERIALISABLE_NAME = 'File Search Context'
    SERIALISABLE_VERSION = 5
    
    def __init__( self, location_context = None, tag_context = None, search_type = SEARCH_TYPE_AND, predicates = None ):
        
        if location_context is None:
            
            location_context = ClientLocation.LocationContext.STATICCreateSimple( CC.COMBINED_LOCAL_MEDIA_SERVICE_KEY )
            
        
        if tag_context is None:
            
            tag_context = TagContext()
            
        
        if predicates is None:
            
            predicates = []
            
        
        self._location_context = location_context
        self._tag_context = tag_context
        
        self._search_type = search_type
        
        self._predicates = predicates
        
        self._search_complete = False
        
        self._InitialiseTemporaryVariables()
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_predicates = [ predicate.GetSerialisableTuple() for predicate in self._predicates ]
        serialisable_location_context = self._location_context.GetSerialisableTuple()
        
        return ( serialisable_location_context, self._tag_context.GetSerialisableTuple(), self._search_type, serialisable_predicates, self._search_complete )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( serialisable_location_context, serialisable_tag_context, self._search_type, serialisable_predicates, self._search_complete ) = serialisable_info
        
        self._location_context = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_location_context )
        self._tag_context = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_tag_context )
        
        self._predicates = [ HydrusSerialisable.CreateFromSerialisableTuple( pred_tuple ) for pred_tuple in serialisable_predicates ]
        
        self._InitialiseTemporaryVariables()
        
    
    def _InitialiseTemporaryVariables( self ):
        
        system_predicates = [ predicate for predicate in self._predicates if predicate.GetType() in SYSTEM_PREDICATE_TYPES ]
        
        self._system_predicates = FileSystemPredicates( system_predicates )
        
        tag_predicates = [ predicate for predicate in self._predicates if predicate.GetType() == PREDICATE_TYPE_TAG ]
        
        self._tags_to_include = []
        self._tags_to_exclude = []
        
        for predicate in tag_predicates:
            
            tag = predicate.GetValue()
            
            if predicate.GetInclusive(): self._tags_to_include.append( tag )
            else: self._tags_to_exclude.append( tag )
            
        
        namespace_predicates = [ predicate for predicate in self._predicates if predicate.GetType() == PREDICATE_TYPE_NAMESPACE ]
        
        self._namespaces_to_include = []
        self._namespaces_to_exclude = []
        
        for predicate in namespace_predicates:
            
            namespace = predicate.GetValue()
            
            if predicate.GetInclusive(): self._namespaces_to_include.append( namespace )
            else: self._namespaces_to_exclude.append( namespace )
            
        
        wildcard_predicates = [ predicate for predicate in self._predicates if predicate.GetType() == PREDICATE_TYPE_WILDCARD ]
        
        self._wildcards_to_include = []
        self._wildcards_to_exclude = []
        
        for predicate in wildcard_predicates:
            
            # this is an important convert. preds store nice looking text, but convert for the actual search
            wildcard = ConvertTagToSearchable( predicate.GetValue() )
            
            if predicate.GetInclusive(): self._wildcards_to_include.append( wildcard )
            else: self._wildcards_to_exclude.append( wildcard )
            
        
        self._or_predicates = [ predicate for predicate in self._predicates if predicate.GetType() == PREDICATE_TYPE_OR_CONTAINER ]
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( file_service_key_hex, tag_service_key_hex, include_current_tags, include_pending_tags, serialisable_predicates, search_complete ) = old_serialisable_info
            
            search_type = SEARCH_TYPE_AND
            
            new_serialisable_info = ( file_service_key_hex, tag_service_key_hex, search_type, include_current_tags, include_pending_tags, serialisable_predicates, search_complete )
            
            return ( 2, new_serialisable_info )
            
        
        if version == 2:
            
            ( file_service_key_hex, tag_service_key_hex, search_type, include_current_tags, include_pending_tags, serialisable_predicates, search_complete ) = old_serialisable_info
            
            # screwed up the serialisation code for the previous update, so these were getting swapped
            
            search_type = SEARCH_TYPE_AND
            include_current_tags = True
            
            new_serialisable_info = ( file_service_key_hex, tag_service_key_hex, search_type, include_current_tags, include_pending_tags, serialisable_predicates, search_complete )
            
            return ( 3, new_serialisable_info )
            
        
        if version == 3:
            
            ( file_service_key_hex, tag_service_key_hex, search_type, include_current_tags, include_pending_tags, serialisable_predicates, search_complete ) = old_serialisable_info
            
            tag_service_key = bytes.fromhex( tag_service_key_hex )
            
            tag_context = TagContext( service_key = tag_service_key, include_current_tags = include_current_tags, include_pending_tags = include_pending_tags )
            
            serialisable_tag_context = tag_context.GetSerialisableTuple()
            
            new_serialisable_info = ( file_service_key_hex, serialisable_tag_context, search_type, serialisable_predicates, search_complete )
            
            return ( 4, new_serialisable_info )
            
        
        if version == 4:
            
            ( file_service_key_hex, serialisable_tag_context, search_type, serialisable_predicates, search_complete ) = old_serialisable_info
            
            file_service_key = bytes.fromhex( file_service_key_hex )
            
            location_context = ClientLocation.LocationContext.STATICCreateSimple( file_service_key )
            
            serialisable_location_context = location_context.GetSerialisableTuple()
            
            new_serialisable_info = ( serialisable_location_context, serialisable_tag_context, search_type, serialisable_predicates, search_complete )
            
            return ( 5, new_serialisable_info )
            
        
    
    def FixMissingServices( self, filter_method ):
        
        self._location_context.FixMissingServices( filter_method )
        self._tag_context.FixMissingServices( filter_method )
        
    
    def GetLocationContext( self ) -> ClientLocation.LocationContext:
        
        return self._location_context
        
    
    def GetNamespacesToExclude( self ): return self._namespaces_to_exclude
    def GetNamespacesToInclude( self ): return self._namespaces_to_include
    def GetORPredicates( self ): return self._or_predicates
    def GetPredicates( self ): return self._predicates
    
    def GetSystemPredicates( self ) -> FileSystemPredicates:
        
        return self._system_predicates
        
    
    def GetTagContext( self ) -> "TagContext":
        
        return self._tag_context
        
    
    def GetTagsToExclude( self ): return self._tags_to_exclude
    def GetTagsToInclude( self ): return self._tags_to_include
    def GetWildcardsToExclude( self ): return self._wildcards_to_exclude
    def GetWildcardsToInclude( self ): return self._wildcards_to_include
    
    def HasNoPredicates( self ):
        
        return len( self._predicates ) == 0
        
    
    def IsComplete( self ):
        
        return self._search_complete
        
    
    def IsJustSystemEverything( self ):
        
        return len( self._predicates ) == 1 and self._system_predicates.HasSystemEverything()
        
    
    def SetComplete( self ):
        
        self._search_complete = True
        
    
    def SetLocationContext( self, location_context: ClientLocation.LocationContext ):
        
        self._location_context = location_context
        
    
    def SetIncludeCurrentTags( self, value ):
        
        self._tag_context.include_current_tags = value
        
    
    def SetIncludePendingTags( self, value ):
        
        self._tag_context.include_pending_tags = value
        
    
    def SetPredicates( self, predicates ):
        
        self._predicates = predicates
        
        self._InitialiseTemporaryVariables()
        
    
    def SetTagServiceKey( self, tag_service_key ):
        
        self._tag_context.service_key = tag_service_key
        self._tag_context.display_service_key = tag_service_key
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_FILE_SEARCH_CONTEXT ] = FileSearchContext

class TagContext( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_tag_context
    SERIALISABLE_NAME = 'Tag Search Context'
    SERIALISABLE_VERSION = 2
    
    def __init__( self, service_key = CC.COMBINED_TAG_SERVICE_KEY, include_current_tags = True, include_pending_tags = True, display_service_key = None ):
        
        self.service_key = service_key
        
        self.include_current_tags = include_current_tags
        self.include_pending_tags = include_pending_tags
        
        if display_service_key is None:
            
            self.display_service_key = self.service_key
            
        else:
            
            self.display_service_key = display_service_key
            
        
    
    def __eq__( self, other ):
        
        if isinstance( other, TagContext ):
            
            return self.__hash__() == other.__hash__()
            
        
        return NotImplemented
        
    
    def __hash__( self ):
        
        return ( self.service_key, self.include_current_tags, self.include_pending_tags, self.display_service_key ).__hash__()
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self.service_key.hex(), self.include_current_tags, self.include_pending_tags, self.display_service_key.hex() )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( encoded_service_key, self.include_current_tags, self.include_pending_tags, encoded_display_service_key ) = serialisable_info
        
        self.service_key = bytes.fromhex( encoded_service_key )
        self.display_service_key = bytes.fromhex( encoded_display_service_key )
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( encoded_service_key, self.include_current_tags, self.include_pending_tags ) = old_serialisable_info
            
            encoded_display_service_key = encoded_service_key
            
            new_serialisable_info = ( encoded_service_key, self.include_current_tags, self.include_pending_tags, encoded_display_service_key )
            
            return ( 2, new_serialisable_info )
            
        
    
    def FixMissingServices( self, filter_method ):
        
        if len( filter_method( [ self.service_key ] ) ) == 0:
            
            self.service_key = CC.COMBINED_TAG_SERVICE_KEY
            
        
    
    def IsAllKnownTags( self ):
        
        return self.service_key == CC.COMBINED_TAG_SERVICE_KEY
        
    
    def ToString( self, name_method ):
        
        return name_method( self.service_key )
        
    
    def ToDictForAPI( self ):
        
        return {
            'service_key' : self.service_key.hex(), 
            'include_current_tags' : self.include_current_tags, 
            'include_pending_tags' : self.include_pending_tags, 
            'display_service_key' : self.display_service_key.hex()
        }
        
    

HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_tag_context ] = TagContext

class FavouriteSearchManager( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_FAVOURITE_SEARCH_MANAGER
    SERIALISABLE_NAME = 'Favourite Search Manager'
    SERIALISABLE_VERSION = 1
    
    def __init__( self ):
        
        HydrusSerialisable.SerialisableBase.__init__( self )
        
        self._favourite_search_rows = []
        
        self._lock = threading.Lock()
        self._dirty = False
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_favourite_search_info = []
        
        for row in self._favourite_search_rows:
            
            ( folder, name, file_search_context, synchronised, media_sort, media_collect ) = row
            
            serialisable_file_search_context = file_search_context.GetSerialisableTuple()
            
            if media_sort is None:
                
                serialisable_media_sort = None
                
            else:
                
                serialisable_media_sort = media_sort.GetSerialisableTuple()
                
            
            if media_collect is None:
                
                serialisable_media_collect = None
                
            else:
                
                serialisable_media_collect = media_collect.GetSerialisableTuple()
                
            
            serialisable_row = ( folder, name, serialisable_file_search_context, synchronised, serialisable_media_sort, serialisable_media_collect )
            
            serialisable_favourite_search_info.append( serialisable_row )
            
        
        return serialisable_favourite_search_info
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        self._favourite_search_rows = []
        
        for serialisable_row in serialisable_info:
            
            ( folder, name, serialisable_file_search_context, synchronised, serialisable_media_sort, serialisable_media_collect ) = serialisable_row
            
            file_search_context = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_file_search_context )
            
            if serialisable_media_sort is None:
                
                media_sort = None
                
            else:
                
                media_sort = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_media_sort )
                
            
            if serialisable_media_collect is None:
                
                media_collect = None
                
            else:
                
                media_collect = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_media_collect )
                
            
            row = ( folder, name, file_search_context, synchronised, media_sort, media_collect )
            
            self._favourite_search_rows.append( row )
            
        
    
    def GetFavouriteSearch( self, desired_folder_name, desired_name ):
        
        with self._lock:
            
            for ( folder, name, file_search_context, synchronised, media_sort, media_collect ) in self._favourite_search_rows:
                
                if folder == desired_folder_name and name == desired_name:
                    
                    return ( file_search_context, synchronised, media_sort, media_collect )
                    
                
            
        
        raise HydrusExceptions.DataMissing( 'Could not find a favourite search named "{}"!'.format( desired_name ) )
        
    
    def GetFavouriteSearchRows( self ):
        
        return list( self._favourite_search_rows )
        
    
    def GetFoldersToNames( self ):
        
        with self._lock:
            
            folders_to_names = collections.defaultdict( list )
            
            for ( folder, name, file_search_context, synchronised, media_sort, media_collect ) in self._favourite_search_rows:
                
                folders_to_names[ folder ].append( name )
                
            
            return folders_to_names
            
        
    
    def IsDirty( self ):
        
        with self._lock:
            
            return self._dirty
            
        
    
    def SetClean( self ):
        
        with self._lock:
            
            self._dirty = False
            
        
    
    def SetDirty( self ):
        
        with self._lock:
            
            self._dirty = True
            
        
    
    def SetFavouriteSearchRows( self, favourite_search_rows ):
        
        with self._lock:
            
            self._favourite_search_rows = list( favourite_search_rows )
            
            self._dirty = True
            
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_FAVOURITE_SEARCH_MANAGER ] = FavouriteSearchManager

class PredicateCount( object ):
    
    def __init__(
        self,
        min_current_count: int,
        min_pending_count: int,
        max_current_count: typing.Optional[ int ],
        max_pending_count: typing.Optional[ int ]
        ):
        
        self.min_current_count = min_current_count
        self.min_pending_count = min_pending_count
        self.max_current_count = max_current_count if max_current_count is not None else min_current_count
        self.max_pending_count = max_pending_count if max_pending_count is not None else min_pending_count
        
    
    def __eq__( self, other ):
        
        if isinstance( other, PredicateCount ):
            
            return self.__hash__() == other.__hash__()
            
        
        return NotImplemented
        
    
    def __hash__( self ):
        
        return (
            self.min_current_count,
            self.min_pending_count,
            self.max_current_count,
            self.max_pending_count
        ).__hash__()
        
    
    def __repr__( self ):
        
        return 'Predicate Count: {}-{} +{}-{}'.format( self.min_current_count, self.max_current_count, self.min_pending_count, self.max_pending_count )
        
    
    def AddCounts( self, count: "PredicateCount" ):
        
        ( self.min_current_count, self.max_current_count ) = ClientData.MergeCounts( self.min_current_count, self.max_current_count, count.min_current_count, count.max_current_count )
        ( self.min_pending_count, self.max_pending_count) = ClientData.MergeCounts( self.min_pending_count, self.max_pending_count, count.min_pending_count, count.max_pending_count )
        
    
    def Duplicate( self ):
        
        return PredicateCount(
            self.min_current_count,
            self.min_pending_count,
            self.max_current_count,
            self.max_pending_count
        )
        
    
    def GetMinCount( self, current_or_pending = None ):
        
        if current_or_pending is None:
            
            return self.min_current_count + self.min_pending_count
            
        elif current_or_pending == HC.CONTENT_STATUS_CURRENT:
            
            return self.min_current_count
            
        elif current_or_pending == HC.CONTENT_STATUS_PENDING:
            
            return self.min_pending_count
            
        
    
    def GetSuffixString( self ) -> str:
        
        suffix_components = []
        
        if self.min_current_count > 0 or self.max_current_count > 0:
            
            number_text = HydrusData.ToHumanInt( self.min_current_count )
            
            if self.max_current_count > self.min_current_count:
                
                number_text = '{}-{}'.format( number_text, HydrusData.ToHumanInt( self.max_current_count ) )
                
            
            suffix_components.append( '({})'.format( number_text ) )
            
        
        if self.min_pending_count > 0 or self.max_pending_count > 0:
            
            number_text = HydrusData.ToHumanInt( self.min_pending_count )
            
            if self.max_pending_count > self.min_pending_count:
                
                number_text = '{}-{}'.format( number_text, HydrusData.ToHumanInt( self.max_pending_count ) )
                
            
            suffix_components.append( '(+{})'.format( number_text ) )
            
        
        return ' '.join( suffix_components )
        
    
    def HasNonZeroCount( self ):
        
        return self.min_current_count > 0 or self.min_pending_count > 0 or self.max_current_count > 0 or self.max_pending_count > 0
        
    
    def HasZeroCount( self ):
        
        return not self.HasNonZeroCount()
        
    
    @staticmethod
    def STATICCreateCurrentCount( current_count ) -> "PredicateCount":
        
        return PredicateCount( current_count, 0, None, None )
        
    
    @staticmethod
    def STATICCreateNullCount() -> "PredicateCount":
        
        return PredicateCount( 0, 0, None, None )
        
    
    @staticmethod
    def STATICCreateStaticCount( current_count, pending_count ) -> "PredicateCount":
        
        return PredicateCount( current_count, pending_count, None, None )
        
    

EDIT_PRED_TYPES = {
    PREDICATE_TYPE_SYSTEM_AGE,
    PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME,
    PREDICATE_TYPE_SYSTEM_MODIFIED_TIME,
    PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME,
    PREDICATE_TYPE_SYSTEM_HEIGHT,
    PREDICATE_TYPE_SYSTEM_WIDTH,
    PREDICATE_TYPE_SYSTEM_RATIO,
    PREDICATE_TYPE_SYSTEM_NUM_PIXELS,
    PREDICATE_TYPE_SYSTEM_DURATION,
    PREDICATE_TYPE_SYSTEM_FRAMERATE,
    PREDICATE_TYPE_SYSTEM_NUM_FRAMES,
    PREDICATE_TYPE_SYSTEM_FILE_SERVICE,
    PREDICATE_TYPE_SYSTEM_KNOWN_URLS,
    PREDICATE_TYPE_SYSTEM_HASH,
    PREDICATE_TYPE_SYSTEM_LIMIT,
    PREDICATE_TYPE_SYSTEM_MIME,
    PREDICATE_TYPE_SYSTEM_RATING,
    PREDICATE_TYPE_SYSTEM_NUM_TAGS,
    PREDICATE_TYPE_SYSTEM_NUM_NOTES,
    PREDICATE_TYPE_SYSTEM_HAS_NOTE_NAME,
    PREDICATE_TYPE_SYSTEM_NUM_WORDS,
    PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES,
    PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA,
    PREDICATE_TYPE_SYSTEM_SIZE,
    PREDICATE_TYPE_SYSTEM_TAG_AS_NUMBER,
    PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_COUNT,
    PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS,
    PREDICATE_TYPE_OR_CONTAINER,
    PREDICATE_TYPE_NAMESPACE,
    PREDICATE_TYPE_WILDCARD,
    PREDICATE_TYPE_TAG
}

class Predicate( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PREDICATE
    SERIALISABLE_NAME = 'File Search Predicate'
    SERIALISABLE_VERSION = 7
    
    def __init__(
        self,
        predicate_type: int = None,
        value: object = None,
        inclusive: bool = True,
        count = None
        ):
        
        if predicate_type == PREDICATE_TYPE_SYSTEM_MIME and value is not None:
            
            value = tuple( sorted( ConvertSpecificFiletypesToSummary( value ) ) )
            
        
        if predicate_type == PREDICATE_TYPE_OR_CONTAINER:
            
            value = list( value )
            
            value.sort( key = lambda p: HydrusTags.ConvertTagToSortable( p.ToString() ) )
            
        
        if isinstance( value, ( list, set ) ):
            
            value = tuple( value )
            
        
        if count is None:
            
            count = PredicateCount.STATICCreateNullCount()
            
        
        self._predicate_type = predicate_type
        self._value = value
        
        self._inclusive = inclusive
        
        self._count = count
        
        self._count_text_suffix = ''
        
        self._ideal_sibling = None
        self._siblings = None
        self._parents = None
        self._parent_predicates = set()
        
        if self._predicate_type == PREDICATE_TYPE_PARENT:
            
            self._parent_key = HydrusData.GenerateKey()
            
        else:
            
            self._parent_key = None
            
        
        self._RecalculateMatchableSearchTexts()
        
        #
        
        self._RecalcPythonHash()
        
    
    def __eq__( self, other ):
        
        if isinstance( other, Predicate ):
            
            if self._predicate_type == PREDICATE_TYPE_PARENT:
                
                return False
                
            
            return self.__hash__() == other.__hash__()
            
        
        return NotImplemented
        
    
    def __hash__( self ):
        
        return self._python_hash
        
    
    def __repr__( self ):
        
        return 'Predicate: ' + str( ( self._predicate_type, self._value, self._inclusive, self._count.GetMinCount() ) )
        
    
    def _RecalcPythonHash( self ):
        
        if self._predicate_type == PREDICATE_TYPE_PARENT:
            
            self._python_hash = self._parent_key.__hash__()
            
        else:
            
            self._python_hash = ( self._predicate_type, self._value, self._inclusive ).__hash__()
            
        
    
    def _GetSerialisableInfo( self ):
        
        if self._predicate_type in ( PREDICATE_TYPE_SYSTEM_RATING, PREDICATE_TYPE_SYSTEM_FILE_SERVICE ):
            
            ( operator, value, service_key ) = self._value
            
            serialisable_value = ( operator, value, service_key.hex() )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES:
            
            ( hashes, max_hamming ) = self._value
            
            serialisable_value = ( [ hash.hex() for hash in hashes ], max_hamming )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA:
            
            ( pixel_hashes, perceptual_hashes, max_hamming ) = self._value
            
            serialisable_value = (
                [ pixel_hash.hex() for pixel_hash in pixel_hashes ],
                [ perceptual_hash.hex() for perceptual_hash in perceptual_hashes ],
                max_hamming
            )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_KNOWN_URLS:
            
            ( operator, rule_type, rule, description ) = self._value
            
            if rule_type in ( 'url_match', 'url_class' ):
                
                serialisable_rule = rule.GetSerialisableTuple()
                
            else:
                
                serialisable_rule = rule
                
            
            serialisable_value = ( operator, rule_type, serialisable_rule, description )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HASH:
            
            ( hashes, hash_type ) = self._value
            
            serialisable_value = ( [ hash.hex() for hash in hashes ], hash_type )
            
        elif self._predicate_type == PREDICATE_TYPE_OR_CONTAINER:
            
            or_predicates = self._value
            
            serialisable_value = HydrusSerialisable.SerialisableList( or_predicates ).GetSerialisableTuple()
            
        else:
            
            serialisable_value = self._value
            
        
        return ( self._predicate_type, serialisable_value, self._inclusive )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._predicate_type, serialisable_value, self._inclusive ) = serialisable_info
        
        if self._predicate_type in ( PREDICATE_TYPE_SYSTEM_RATING, PREDICATE_TYPE_SYSTEM_FILE_SERVICE ):
            
            ( operator, value, service_key ) = serialisable_value
            
            self._value = ( operator, value, bytes.fromhex( service_key ) )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES:
            
            ( serialisable_hashes, max_hamming ) = serialisable_value
            
            self._value = ( tuple( [ bytes.fromhex( serialisable_hash ) for serialisable_hash in serialisable_hashes ] ) , max_hamming )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA:
            
            ( serialisable_pixel_hashes, serialisable_perceptual_hashes, max_hamming ) = serialisable_value
            
            self._value = (
                tuple( [ bytes.fromhex( serialisable_pixel_hash ) for serialisable_pixel_hash in serialisable_pixel_hashes ] ),
                tuple( [ bytes.fromhex( serialisable_perceptual_hash ) for serialisable_perceptual_hash in serialisable_perceptual_hashes ] ),
                max_hamming
            )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_KNOWN_URLS:
            
            ( operator, rule_type, serialisable_rule, description ) = serialisable_value
            
            if rule_type in ( 'url_match', 'url_class' ):
                
                rule = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_rule )
                
            else:
                
                rule = serialisable_rule
                
            
            self._value = ( operator, rule_type, rule, description )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HASH:
            
            ( serialisable_hashes, hash_type ) = serialisable_value
            
            self._value = ( tuple( [ bytes.fromhex( serialisable_hash ) for serialisable_hash in serialisable_hashes ] ), hash_type )
            
        elif self._predicate_type in ( PREDICATE_TYPE_SYSTEM_AGE, PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME, PREDICATE_TYPE_SYSTEM_MODIFIED_TIME, PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME ):
            
            ( operator, age_type, age_value ) = serialisable_value
            
            self._value = ( operator, age_type, tuple( age_value ) )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS:
            
            ( view_type, viewing_locations, operator, viewing_value ) = serialisable_value
            
            self._value = ( view_type, tuple( viewing_locations ), operator, viewing_value )
            
        elif self._predicate_type == PREDICATE_TYPE_OR_CONTAINER:
            
            serialisable_or_predicates = serialisable_value
            
            self._value = tuple( sorted( HydrusSerialisable.CreateFromSerialisableTuple( serialisable_or_predicates ), key = lambda p: HydrusTags.ConvertTagToSortable( p.ToString() ) ) )
            
        else:
            
            self._value = serialisable_value
            
            if self._predicate_type == PREDICATE_TYPE_SYSTEM_MIME and self._value is not None:
                
                self._value = tuple( sorted( ConvertSpecificFiletypesToSummary( self._value ) ) )
                
            
        
        if isinstance( self._value, list ):
            
            self._value = tuple( self._value )
            
        
        self._RecalcPythonHash()
        
    
    def _RecalculateMatchableSearchTexts( self ):
        
        if self._predicate_type == PREDICATE_TYPE_TAG:
            
            self._matchable_search_texts = { self._value }
            
            if self._siblings is not None:
                
                self._matchable_search_texts.update( self._siblings )
                
            
        else:
            
            self._matchable_search_texts = set()
            
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( predicate_type, serialisable_value, inclusive ) = old_serialisable_info
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_AGE:
                
                ( operator, years, months, days, hours ) = serialisable_value
                
                serialisable_value = ( operator, 'delta', ( years, months, days, hours ) )
                
            
            new_serialisable_info = ( predicate_type, serialisable_value, inclusive )
            
            return ( 2, new_serialisable_info )
            
        
        if version == 2:
            
            ( predicate_type, serialisable_value, inclusive ) = old_serialisable_info
            
            if predicate_type in ( PREDICATE_TYPE_SYSTEM_HASH, PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES ):
                
                # other value is either hash type or max hamming distance
                
                ( serialisable_hash, other_value ) = serialisable_value
                
                serialisable_hashes = ( serialisable_hash, )
                
                serialisable_value = ( serialisable_hashes, other_value )
                
            
            new_serialisable_info = ( predicate_type, serialisable_value, inclusive )
            
            return ( 3, new_serialisable_info )
            
        
        if version == 3:
            
            ( predicate_type, serialisable_value, inclusive ) = old_serialisable_info
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_NUM_TAGS:
                
                ( operator, num ) = serialisable_value
                
                namespace = '*'
                
                serialisable_value = ( namespace, operator, num )
                
            
            new_serialisable_info = ( predicate_type, serialisable_value, inclusive )
            
            return ( 4, new_serialisable_info )
            
        
        if version == 4:
            
            ( predicate_type, serialisable_value, inclusive ) = old_serialisable_info
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_MIME:
                
                specific_mimes = serialisable_value
                
                summary_mimes = ConvertSpecificFiletypesToSummary( specific_mimes )
                
                serialisable_value = tuple( sorted( summary_mimes ) )
                
            
            new_serialisable_info = ( predicate_type, serialisable_value, inclusive )
            
            return ( 5, new_serialisable_info )
            
        
        if version == 5:
            
            ( predicate_type, serialisable_value, inclusive ) = old_serialisable_info
            
            if predicate_type in ( PREDICATE_TYPE_SYSTEM_AGE, PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME, PREDICATE_TYPE_SYSTEM_MODIFIED_TIME, PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME ):
                
                ( operator, age_type, age_value ) = serialisable_value
                
                if age_type == 'date':
                    
                    ( year, month, day ) = age_value
                    
                    hour = 0
                    minute = 0
                    
                    age_value = ( year, month, day, hour, minute )
                    
                    serialisable_value = ( operator, age_type, age_value )
                    
                
            
            new_serialisable_info = ( predicate_type, serialisable_value, inclusive )
            
            return ( 6, new_serialisable_info )
            
        
        if version == 6:
            
            ( predicate_type, serialisable_value, inclusive ) = old_serialisable_info
            
            if predicate_type == PREDICATE_TYPE_SYSTEM_MIME:
                
                mimes = list( serialisable_value )
                
                if HC.GENERAL_APPLICATION in mimes:
                    
                    mimes.append( HC.GENERAL_APPLICATION_ARCHIVE )
                    mimes.append( HC.GENERAL_IMAGE_PROJECT )
                    
                
                mimes = tuple( mimes )
                
                serialisable_value = mimes
                
            
            new_serialisable_info = ( predicate_type, serialisable_value, inclusive )
            
            return ( 7, new_serialisable_info )
            
        
    
    def GetCopy( self ):
        
        return Predicate( self._predicate_type, self._value, self._inclusive, count = self._count.Duplicate() )
        
    
    def GetCount( self ):
        
        return self._count
        
    
    def GetCountlessCopy( self ):
        
        return Predicate( self._predicate_type, self._value, self._inclusive )
        
    
    def GetNamespace( self ):
        
        if self._predicate_type in SYSTEM_PREDICATE_TYPES:
            
            return 'system'
            
        elif self._predicate_type == PREDICATE_TYPE_NAMESPACE:
            
            namespace = self._value
            
            return namespace
            
        elif self._predicate_type in ( PREDICATE_TYPE_PARENT, PREDICATE_TYPE_TAG, PREDICATE_TYPE_WILDCARD ):
            
            tag_analogue = self._value
            
            ( namespace, subtag ) = HydrusTags.SplitTag( tag_analogue )
            
            if '*' in namespace:
                
                return '*'
                
            
            return namespace
            
        else:
            
            return ''
            
        
    
    def GetIdealPredicate( self ):
        
        if self._ideal_sibling is None:
            
            return None
            
        else:
            
            return Predicate( PREDICATE_TYPE_TAG, self._ideal_sibling, self._inclusive )
            
        
    
    def GetIdealSibling( self ):
        
        return self._ideal_sibling
        
    
    def GetInclusive( self ):
        
        # patch from an upgrade mess-up ~v144
        if not hasattr( self, '_inclusive' ):
            
            if self._predicate_type not in SYSTEM_PREDICATE_TYPES:
                
                ( operator, value ) = self._value
                
                self._value = value
                
                self._inclusive = operator == '+'
                
            else:
                
                self._inclusive = True
                
            
            self._RecalcPythonHash()
            
        
        return self._inclusive
        
    
    def GetInfo( self ):
        
        return ( self._predicate_type, self._value, self._inclusive )
        
    
    def GetInverseCopy( self ):
        
        if self._predicate_type == PREDICATE_TYPE_SYSTEM_ARCHIVE:
            
            return Predicate( PREDICATE_TYPE_SYSTEM_INBOX )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_INBOX:
            
            return Predicate( PREDICATE_TYPE_SYSTEM_ARCHIVE )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_LOCAL:
            
            return Predicate( PREDICATE_TYPE_SYSTEM_NOT_LOCAL )
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NOT_LOCAL:
            
            return Predicate( PREDICATE_TYPE_SYSTEM_LOCAL )
            
        elif self._predicate_type in ( PREDICATE_TYPE_TAG, PREDICATE_TYPE_NAMESPACE, PREDICATE_TYPE_WILDCARD ):
            
            return Predicate( self._predicate_type, self._value, not self._inclusive )
            
        elif self._predicate_type in ( PREDICATE_TYPE_SYSTEM_HAS_AUDIO, PREDICATE_TYPE_SYSTEM_HAS_TRANSPARENCY, PREDICATE_TYPE_SYSTEM_HAS_EXIF, PREDICATE_TYPE_SYSTEM_HAS_HUMAN_READABLE_EMBEDDED_METADATA, PREDICATE_TYPE_SYSTEM_HAS_ICC_PROFILE, PREDICATE_TYPE_SYSTEM_HAS_FORCED_FILETYPE ):
            
            return Predicate( self._predicate_type, not self._value )
            
        elif self._predicate_type in ( PREDICATE_TYPE_SYSTEM_NUM_NOTES, PREDICATE_TYPE_SYSTEM_NUM_WORDS, PREDICATE_TYPE_SYSTEM_NUM_FRAMES, PREDICATE_TYPE_SYSTEM_DURATION ):
            
            ( operator, value ) = self._value
            
            number_test = NumberTest.STATICCreateFromCharacters( operator, value )
            
            if number_test.IsZero():
                
                return Predicate( self._predicate_type, ( '>', 0 ) )
                
            elif number_test.IsAnythingButZero():
                
                return Predicate( self._predicate_type, ( '=', 0 ) )
                
            else:
                
                return None
                
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_KING:
            
            return Predicate( self._predicate_type, not self._value )
            
        else:
            
            return None
            
        
    
    def GetMatchableSearchTexts( self ):
        
        return self._matchable_search_texts
        
    
    def GetParentPredicates( self ):
        
        return self._parent_predicates
        
    
    def GetTextsAndNamespaces( self, render_for_user: bool, or_under_construction: bool = False ):
        
        if self._predicate_type == PREDICATE_TYPE_OR_CONTAINER:
            
            or_connector = HG.client_controller.new_options.GetString( 'or_connector' )
            or_connector_namespace = HG.client_controller.new_options.GetNoneableString( 'or_connector_custom_namespace_colour' )
            
            texts_and_namespaces = []
            
            for or_predicate in self._value:
                
                texts_and_namespaces.append( ( or_predicate.ToString(), 'namespace', or_predicate.GetNamespace() ) )
                
                texts_and_namespaces.append( ( or_connector, 'or', or_connector_namespace ) )
                
            
            if not or_under_construction:
                
                texts_and_namespaces = texts_and_namespaces[ : -1 ]
                
            
        else:
            
            texts_and_namespaces = [ ( self.ToString( render_for_user = render_for_user ), 'namespace', self.GetNamespace() ) ]
            
        
        return texts_and_namespaces
        
    
    def GetType( self ):
        
        return self._predicate_type
        
    
    def GetUnnamespacedCopy( self ):
        
        if self._predicate_type == PREDICATE_TYPE_TAG:
            
            ( namespace, subtag ) = HydrusTags.SplitTag( self._value )
            
            return Predicate( self._predicate_type, subtag, self._inclusive, count = self._count.Duplicate() )
            
        
        return self.GetCopy()
        
    
    def GetValue( self ):
        
        return self._value
        
    
    def HasIdealSibling( self ):
        
        return self._ideal_sibling is not None
        
    
    def HasParentPredicates( self ):
        
        return len( self._parent_predicates ) > 0
        
    
    def IsEditable( self ):
        
        return self._predicate_type in EDIT_PRED_TYPES
        
    
    def IsInclusive( self ):
        
        return self._inclusive
        
    
    def IsInvertible( self ):
        
        return self.GetInverseCopy() is not None
        
    
    def IsMutuallyExclusive( self, predicate ):
        
        if self._predicate_type == PREDICATE_TYPE_SYSTEM_EVERYTHING:
            
            return True
            
        
        if self.IsInvertible() and predicate == self.GetInverseCopy():
            
            return True
            
        
        my_type = self._predicate_type
        other_type = predicate.GetType()
        
        if my_type == other_type:
            
            if my_type in ( PREDICATE_TYPE_SYSTEM_LIMIT, PREDICATE_TYPE_SYSTEM_HASH ):
                
                return True
                
            
        
        return False
        
    
    def IsORPredicate( self ):
        
        return self._predicate_type == PREDICATE_TYPE_OR_CONTAINER
        
    
    def IsUIEditable( self, ideal_predicate: "Predicate" ) -> bool:
        
        # bleh
        
        if self._predicate_type != ideal_predicate.GetType():
            
            return False
            
        
        ideal_value = ideal_predicate.GetValue()
        
        if self._value is None and ideal_value is not None:
            
            return False
            
        
        if self._predicate_type in ( PREDICATE_TYPE_SYSTEM_AGE, PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME, PREDICATE_TYPE_SYSTEM_MODIFIED_TIME, PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME ):
            
            # age_type
            if self._value[1] != ideal_value[1]:
                
                return False
                
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS:
            
            # view_type
            if self._value[0] != ideal_value[0]:
                
                return False
                
            
        elif self._predicate_type == PREDICATE_TYPE_SYSTEM_KNOWN_URLS:
            
            # rule type
            if self._value[1] != ideal_value[1]:
                
                return False
                
            
        
        return True
        
    
    def SetCount( self, count: PredicateCount ):
        
        self._count = count
        
    
    def SetCountTextSuffix( self, suffix: str ):
        
        self._count_text_suffix = suffix
        
    
    def SetIdealSibling( self, tag: str ):
        
        self._ideal_sibling = tag
        
    
    def SetInclusive( self, inclusive ):
        
        self._inclusive = inclusive
        
        self._RecalcPythonHash()
        
    
    def SetKnownParents( self, parents: typing.Set[ str ] ):
        
        self._parents = parents
        
        self._parent_predicates = [ Predicate( PREDICATE_TYPE_PARENT, parent ) for parent in self._parents ]
        
    
    def SetKnownSiblings( self, siblings: typing.Set[ str ] ):
        
        self._siblings = siblings
        
        self._RecalculateMatchableSearchTexts()
        
    
    def ToString( self, with_count: bool = True, tag_display_type: int = ClientTags.TAG_DISPLAY_DISPLAY_ACTUAL, render_for_user: bool = False, or_under_construction: bool = False ) -> str:
        
        base = ''
        count_text = ''
        
        if with_count:
            
            suffix = self._count.GetSuffixString()
            
            if len( suffix ) > 0:
                
                count_text += ' {}'.format( suffix )
                
            
            if self._count_text_suffix != '':
                
                count_text += ' ({})'.format( self._count_text_suffix )
                
            
        
        if self._predicate_type in SYSTEM_PREDICATE_TYPES:
            
            if self._predicate_type == PREDICATE_TYPE_SYSTEM_EVERYTHING: base = 'everything'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_INBOX: base = 'inbox'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_ARCHIVE: base = 'archive'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_UNTAGGED: base = 'untagged'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_LOCAL: base = 'local'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NOT_LOCAL: base = 'not local'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_PROPERTIES: base = 'file properties'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_DIMENSIONS: base = 'dimensions'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO: base = 'similar files'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_TIME: base = 'time'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NOTES: base = 'notes'
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS: base = 'file relationships'
            elif self._predicate_type in ( PREDICATE_TYPE_SYSTEM_WIDTH, PREDICATE_TYPE_SYSTEM_HEIGHT, PREDICATE_TYPE_SYSTEM_NUM_NOTES, PREDICATE_TYPE_SYSTEM_NUM_WORDS, PREDICATE_TYPE_SYSTEM_NUM_FRAMES ):
                
                has_phrase = None
                not_has_phrase = None
                
                if self._predicate_type == PREDICATE_TYPE_SYSTEM_WIDTH:
                    
                    base = 'width'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HEIGHT:
                    
                    base = 'height'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NUM_NOTES:
                    
                    base = 'number of notes'
                    has_phrase = ': has notes'
                    not_has_phrase = ': no notes'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NUM_WORDS:
                    
                    base = 'number of words'
                    has_phrase = ': has words'
                    not_has_phrase = ': no words'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NUM_FRAMES:
                    
                    base = 'number of frames'
                    has_phrase = ': has frames'
                    not_has_phrase = ': no frames'
                    
                
                if self._value is not None:
                    
                    ( operator, value ) = self._value
                    
                    if operator == '>' and value == 0 and has_phrase is not None:
                        
                        base += has_phrase
                        
                    elif ( ( operator == '=' and value == 0 ) or ( operator == '<' and value == 1 ) ) and not_has_phrase is not None:
                        
                        base += not_has_phrase
                        
                    else:
                        
                        base += ' {} {}'.format( operator, HydrusData.ToHumanInt( value ) )
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_DURATION:
                
                base = 'duration'
                
                if self._value is not None:
                    
                    ( operator, value ) = self._value
                    
                    if operator == '>' and value == 0:
                        
                        base = 'has duration'
                        
                    elif operator == '=' and value == 0:
                        
                        base = 'no duration'
                        
                    else:
                        
                        base += ' {} {}'.format( operator, HydrusTime.MillisecondsToPrettyTime( value ) )
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FRAMERATE:
                
                base = 'framerate'
                
                if self._value is not None:
                    
                    ( operator, value ) = self._value
                    
                    base += ' {} {}fps'.format( operator, HydrusData.ToHumanInt( value ) )
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_NOTE_NAME:
                
                base = 'has note'
                
                if self._value is not None:
                    
                    ( operator, name ) = self._value
                    
                    if operator:
                        
                        base = 'has note with name "{}"'.format( name )
                        
                    else:
                        
                        base = 'does not have note with name "{}"'.format( name )
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NUM_TAGS:
                
                base = 'number of tags'
                
                if self._value is not None:
                    
                    ( namespace, operator, value ) = self._value
                    
                    number_test = NumberTest.STATICCreateFromCharacters( operator, value )
                    
                    any_namespace = namespace is None or namespace == '*'
                    
                    if number_test.IsAnythingButZero():
                        
                        if any_namespace:
                            
                            base = 'has tags'
                            
                        else:
                            
                            # shouldn't see this, as it'll be converted to a namespace pred, but here anyway
                            base = 'has {} tags'.format( ClientTags.RenderNamespaceForUser( namespace ) )
                            
                        
                    elif number_test.IsZero():
                        
                        if any_namespace:
                            
                            base = 'untagged'
                            
                        else:
                            
                            # shouldn't see this, as it'll be converted to a namespace pred, but here anyway
                            base = 'no {} tags'.format( ClientTags.RenderNamespaceForUser( namespace ) )
                            
                        
                    else:
                        
                        if not any_namespace:
                            
                            base = 'number of {} tags'.format( ClientTags.RenderNamespaceForUser( namespace ) )
                            
                        
                        base += ' {} {}'.format( operator, HydrusData.ToHumanInt( value ) )
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_RATIO:
                
                base = 'ratio'
                
                if self._value is not None:
                    
                    ( operator, ratio_width, ratio_height ) = self._value
                    
                    base += ' ' + operator + ' ' + str( ratio_width ) + ':' + str( ratio_height )
                    
                    if ratio_width == 1 and ratio_height == 1:
                        
                        if operator == 'wider than':
                            
                            base = 'ratio is landscape'
                            
                        elif operator == 'taller than':
                            
                            base = 'ratio is portrait'
                            
                        elif operator == '=':
                            
                            base = 'ratio is square'
                            
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIZE:
                
                base = 'filesize'
                
                if self._value is not None:
                    
                    ( operator, size, unit ) = self._value
                    
                    base += ' ' + operator + ' ' + str( size ) + HydrusData.ConvertIntToUnit( unit )
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_LIMIT:
                
                base = 'limit'
                
                if self._value is not None:
                    
                    value = self._value
                    
                    base += ' is ' + HydrusData.ToHumanInt( value )
                    
                
            elif self._predicate_type in ( PREDICATE_TYPE_SYSTEM_AGE, PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME, PREDICATE_TYPE_SYSTEM_MODIFIED_TIME, PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME  ):
                
                if self._predicate_type == PREDICATE_TYPE_SYSTEM_AGE:
                    
                    base = 'import time'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_LAST_VIEWED_TIME:
                    
                    base = 'last viewed time'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_MODIFIED_TIME:
                    
                    base = 'modified time'
                    
                elif self._predicate_type == PREDICATE_TYPE_SYSTEM_ARCHIVED_TIME:
                    
                    base = 'archived time'
                    
                
                if self._value is not None:
                    
                    ( operator, age_type, age_value ) = self._value
                    
                    if age_type == 'delta':
                        
                        ( years, months, days, hours ) = age_value
                        
                        str_components = []
                        
                        for ( quantity, label ) in [
                            ( years, 'year' ),
                            ( months, 'month' ),
                            ( days, 'day' ),
                            ( hours, 'hour' ),
                        ]:
                            
                            if quantity > 0:
                                
                                str_component = '{} {}'.format( HydrusData.ToHumanInt( quantity ), label )
                                
                                if quantity > 1:
                                    
                                    str_component += 's'
                                    
                                
                                str_components.append( str_component )
                                
                            
                            if len( str_components ) == 2:
                                
                                break
                                
                            
                        
                        nice_date_string = ' '.join( str_components )
                        
                        if operator == '<':
                            
                            pretty_operator = 'since'
                            
                        elif operator == '>':
                            
                            pretty_operator = 'before'
                            
                        elif operator == HC.UNICODE_APPROX_EQUAL:
                            
                            pretty_operator = 'around'
                            
                        else:
                            
                            pretty_operator = 'unknown operator'
                            
                        
                        base += ': {} {} ago'.format( pretty_operator, nice_date_string )
                        
                    elif age_type == 'date':
                        
                        ( year, month, day, hour, minute ) = age_value
                        
                        dt = datetime.datetime( year, month, day, hour, minute )
                        
                        if operator == '<':
                            
                            pretty_operator = 'before '
                            
                        elif operator == '>':
                            
                            pretty_operator = 'since '
                            
                        elif operator == '=':
                            
                            pretty_operator = 'on the day of '
                            
                        elif operator == HC.UNICODE_APPROX_EQUAL:
                            
                            pretty_operator = 'a month either side of '
                            
                        
                        include_24h_time = operator != '=' and ( hour > 0 or minute > 0 )
                        
                        base += ': ' + pretty_operator + HydrusTime.DateTimeToPrettyTime( dt, include_24h_time = include_24h_time )
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_NUM_PIXELS:
                
                base = 'number of pixels'
                
                if self._value is not None:
                    
                    ( operator, num_pixels, unit ) = self._value
                    
                    base += ' ' + operator + ' ' + str( num_pixels ) + ' ' + HydrusData.ConvertIntToPixels( unit )
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_KNOWN_URLS:
                
                base = 'known url'
                
                if self._value is not None:
                    
                    ( operator, rule_type, rule, description ) = self._value
                    
                    base = description
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_AUDIO:
                
                base = 'has audio'
                
                if self._value is not None:
                    
                    has_audio = self._value
                    
                    if not has_audio:
                        
                        base = 'no audio'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_TRANSPARENCY:
                
                base = 'has transparency'
                
                if self._value is not None:
                    
                    has_transparency = self._value
                    
                    if not has_transparency:
                        
                        base = 'no transparency'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_EXIF:
                
                base = 'has exif'
                
                if self._value is not None:
                    
                    has_exif = self._value
                    
                    if not has_exif:
                        
                        base = 'no exif'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_HUMAN_READABLE_EMBEDDED_METADATA:
                
                base = 'has human-readable embedded metadata'
                
                if self._value is not None:
                    
                    has_human_readable_embedded_metadata = self._value
                    
                    if not has_human_readable_embedded_metadata:
                        
                        base = 'no human-readable embedded metadata'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_ICC_PROFILE:
                
                base = 'has icc profile'
                
                if self._value is not None:
                    
                    has_icc_profile = self._value
                    
                    if not has_icc_profile:
                        
                        base = 'no icc profile'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HAS_FORCED_FILETYPE:
                
                base = 'has forced filetype'
                
                if self._value is not None:
                    
                    has_forced_filetype = self._value
                    
                    if not has_forced_filetype:
                        
                        base = 'no forced filetype'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_HASH:
                
                base = 'hash'
                
                if self._value is not None:
                    
                    ( hashes, hash_type ) = self._value
                    
                    if self._inclusive:
                        
                        is_phrase = 'is'
                        
                    else:
                        
                        is_phrase = 'is not'
                        
                    
                    if len( hashes ) == 1:
                        
                        base = '{} hash {} {}'.format( hash_type, is_phrase, hashes[0].hex() )
                        
                    else:
                        
                        base = '{} hash {} in {} hashes'.format( hash_type, is_phrase, HydrusData.ToHumanInt( len( hashes ) ) )
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_MIME:
                
                base = 'filetype'
                
                if self._value is not None:
                    
                    summary_mimes = self._value
                    
                    mime_text = ConvertSummaryFiletypesToString( summary_mimes )
                    
                    base += ' is ' + mime_text
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_RATING:
                
                base = 'rating'
                
                if self._value is not None:
                    
                    ( operator, value, service_key ) = self._value
                    
                    try:
                        
                        service = HG.client_controller.services_manager.GetService( service_key )
                        
                        name = service.GetName()
                        
                        if value == 'rated':
                            
                            base = 'has a rating for {}'.format( name )
                            
                        elif value == 'not rated':
                            
                            base = 'does not have a rating for {}'.format( name )
                            
                        else:
                            
                            pretty_value = service.ConvertNoneableRatingToString( value )
                            
                            base += ' for {} {} {}'.format( service.GetName(), operator, pretty_value )
                            
                        
                    except HydrusExceptions.DataMissing:
                        
                        base = 'unknown rating service system predicate'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_FILES:
                
                base = 'similar to'
                
                if self._value is not None:
                    
                    ( hashes, max_hamming ) = self._value
                    
                    base += ' {} files using max hamming of {}'.format( HydrusData.ToHumanInt( len( hashes ) ), max_hamming )
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_SIMILAR_TO_DATA:
                
                base = 'similar to'
                
                if self._value is not None:
                    
                    ( pixel_hashes, perceptual_hashes, max_hamming ) = self._value
                    
                    base += ' {} similar data hashes using max hamming of {}'.format( HydrusData.ToHumanInt( len( pixel_hashes ) + len( perceptual_hashes ) ), max_hamming )
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_SERVICE:
                
                if self._value is None:
                    
                    base = 'file service'
                    
                else:
                    
                    ( operator, status, service_key ) = self._value
                    
                    base = 'is' if operator else 'is not'
                    
                    if status == HC.CONTENT_STATUS_CURRENT:
                        
                        base += ' currently in '
                        
                    elif status == HC.CONTENT_STATUS_DELETED:
                        
                        base += ' deleted from '
                        
                    elif status == HC.CONTENT_STATUS_PENDING:
                        
                        base += ' pending to '
                        
                    elif status == HC.CONTENT_STATUS_PETITIONED:
                        
                        base += ' petitioned from '
                        
                    
                    try:
                        
                        service = HG.client_controller.services_manager.GetService( service_key )
                        
                        base += service.GetName()
                        
                    except HydrusExceptions.DataMissing:
                        
                        base = 'unknown file service system predicate'
                        
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_TAG_AS_NUMBER:
                
                base = 'tag as number'
                
                if self._value is not None:
                    
                    ( namespace, operator, num ) = self._value
                    
                    if namespace == '*':
                        
                        n_text = 'any namespace'
                        
                    elif namespace == '':
                        
                        n_text = 'unnamespaced'
                        
                    else:
                        
                        n_text = namespace
                        
                    
                    if operator == HC.UNICODE_APPROX_EQUAL:
                        
                        o_text = 'about'
                        
                    elif operator == '<':
                        
                        o_text = 'less than'
                        
                    elif operator == '>':
                        
                        o_text = 'more than'
                        
                    else:
                        
                        o_text = 'unknown'
                        
                    
                    base = f'{base}: {n_text} {o_text} {HydrusData.ToHumanInt( num )}'
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_COUNT:
                
                base = 'num file relationships'
                
                if self._value is not None:
                    
                    ( operator, num_relationships, dupe_type ) = self._value
                    
                    if operator == HC.UNICODE_APPROX_EQUAL:
                        
                        o_text = ' about '
                        
                    elif operator == '<':
                        
                        o_text = ' less than '
                        
                    elif operator == '>':
                        
                        o_text = ' more than '
                        
                    elif operator == '=':
                        
                        o_text = ' '
                        
                    
                    base += ' - has' + o_text + HydrusData.ToHumanInt( num_relationships ) + ' ' + HC.duplicate_type_string_lookup[ dupe_type ]
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_RELATIONSHIPS_KING:
                
                base = ''
                
                if self._value is not None:
                    
                    king = self._value
                    
                    if king:
                        
                        o_text = 'is the best quality file of its duplicate group'
                        
                    else:
                        
                        o_text = 'is not the best quality file of its duplicate group'
                        
                    
                    base += o_text
                    
                
            elif self._predicate_type == PREDICATE_TYPE_SYSTEM_FILE_VIEWING_STATS:
                
                base = 'file viewing statistics'
                
                if self._value is not None:
                    
                    ( view_type, viewing_locations, operator, viewing_value ) = self._value
                    
                    include_media = 'media' in viewing_locations
                    include_previews = 'preview' in viewing_locations
                    
                    if include_media and include_previews:
                        
                        domain = 'all'
                        
                    elif include_media:
                        
                        domain = 'media'
                        
                    elif include_previews:
                        
                        domain = 'preview'
                        
                    else:
                        
                        domain = 'unknown'
                        
                    
                    if view_type == 'views':
                        
                        value_string = HydrusData.ToHumanInt( viewing_value )
                        
                    elif view_type == 'viewtime':
                        
                        value_string = HydrusTime.TimeDeltaToPrettyTimeDelta( viewing_value )
                        
                    
                    base = '{} {} {} {}'.format( domain, view_type, operator, value_string )
                    
                
            
            base = HydrusTags.CombineTag( 'system', base )
            
            base = ClientTags.RenderTag( base, render_for_user )
            
            base += count_text
            
        elif self._predicate_type == PREDICATE_TYPE_TAG:
            
            tag = self._value
            
            if not self._inclusive: base = '-'
            else: base = ''
            
            base += ClientTags.RenderTag( tag, render_for_user )
            
            base += count_text
            
        elif self._predicate_type == PREDICATE_TYPE_PARENT:
            
            base = '    '
            
            tag = self._value
            
            base += ClientTags.RenderTag( tag, render_for_user )
            
            base += count_text
            
        elif self._predicate_type == PREDICATE_TYPE_NAMESPACE:
            
            namespace = self._value
            
            if not self._inclusive: base = '-'
            else: base = ''
            
            pretty_namespace = ClientTags.RenderNamespaceForUser( namespace )
            
            anything_tag = HydrusTags.CombineTag( pretty_namespace, '*anything*' )
            
            anything_tag = ClientTags.RenderTag( anything_tag, render_for_user )
            
            base += anything_tag
            
        elif self._predicate_type == PREDICATE_TYPE_WILDCARD:
            
            if self._value.startswith( '*:' ):
                
                ( any_namespace, subtag ) = HydrusTags.SplitTag( self._value )
                
                wildcard = '{} (any namespace)'.format( subtag )
                
            else:
                
                wildcard = self._value + ' (wildcard search)'
                
            
            if not self._inclusive:
                
                base = '-'
                
            else:
                
                base = ''
                
            
            base += wildcard
            
        elif self._predicate_type == PREDICATE_TYPE_OR_CONTAINER:
            
            or_predicates = self._value
            
            base = ''
            
            if or_under_construction:
                
                base += 'OR: '
                
            
            base += ' OR '.join( ( or_predicate.ToString( render_for_user = render_for_user ) for or_predicate in or_predicates ) ) # pylint: disable=E1101
            
        elif self._predicate_type == PREDICATE_TYPE_LABEL:
            
            label = self._value
            
            base = label
            
        
        return base
        
    

def FilterPredicatesBySearchText( service_key, search_text, predicates: typing.Collection[ Predicate ] ):
    
    def compile_re( s ):
        
        regular_parts_of_s = s.split( '*' )
        
        escaped_parts_of_s = [ re.escape( rpos ) for rpos in regular_parts_of_s ]
        
        s = '.*'.join( escaped_parts_of_s )
        
        # \A is start of string
        # \Z is end of string
        # \s is whitespace
        
        # ':' is no longer escaped to '\:' in py 3.7 lmaooooo, so some quick hackery
        if re.escape( ':' ) == r'\:':
            
            s = s.replace( r'\:', ':' )
            
        
        if ':' in s:
            
            ( namespace, subtag ) = s.split( ':', 1 )
            
            if namespace == '.*':
                
                beginning = r'(\A|:|\s)'
                s = subtag
                
            else:
                
                beginning = r'\A'
                s = r'{}:(.*\s)?{}'.format( namespace, subtag )
                
            
        elif s.startswith( '.*' ):
            
            beginning = r'(\A|:)'
            
        else:
            
            beginning = r'(\A|:|\s)'
            
        
        if s.endswith( '.*' ):
            
            end = r'\Z' # end of string
            
        else:
            
            end = r'(\s|\Z)' # whitespace or end of string
            
        
        return re.compile( beginning + s + end )
        
    
    re_predicate = compile_re( search_text )
    
    matches = []
    
    for predicate in predicates:
        
        ( predicate_type, value, inclusive ) = predicate.GetInfo()
        
        if predicate_type != PREDICATE_TYPE_TAG:
            
            continue
            
        
        possible_tags = predicate.GetMatchableSearchTexts()
        
        searchable_tags = { ConvertTagToSearchable( possible_tag ) for possible_tag in possible_tags }
        
        for searchable_tag in searchable_tags:
            
            if re_predicate.search( searchable_tag ) is not None:
                
                matches.append( predicate )
                
                break
                
            
        
    
    return matches
    

HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PREDICATE ] = Predicate

SYSTEM_PREDICATE_INBOX = Predicate( PREDICATE_TYPE_SYSTEM_INBOX, None )

SYSTEM_PREDICATE_ARCHIVE = Predicate( PREDICATE_TYPE_SYSTEM_ARCHIVE, None )

SYSTEM_PREDICATE_LOCAL = Predicate( PREDICATE_TYPE_SYSTEM_LOCAL, None )

SYSTEM_PREDICATE_NOT_LOCAL = Predicate( PREDICATE_TYPE_SYSTEM_NOT_LOCAL, None )
