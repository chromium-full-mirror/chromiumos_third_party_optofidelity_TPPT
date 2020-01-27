"""
Copyright (c) 2019, OptoFidelity OY

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    3. All advertising materials mentioning features or use of this software must display the following acknowledgement: This product includes software developed by the OptoFidelity OY.
    4. Neither the name of the OptoFidelity OY nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import xml.etree.ElementTree as ElementTree

# class for cluster variable handling
class Clusterizer:

    def __init__( self, clusterXml=None ):

        # create empty cluster, if none is specified
        if clusterXml == None:
            clusterXml = """<Cluster>
                                <Name>MsgCluster</Name>
                                <NumElts>5</NumElts>
                                <EW>
                                    <Name>Sender</Name>
                                    <Choice>Manager</Choice>
                                    <Choice>DAQ</Choice>
                                    <Choice>Duts</Choice>
                                    <Choice>Robots</Choice>
                                    <Choice>Script</Choice>
                                    <Choice>Camera</Choice>
                                    <Val>4</Val>
                                </EW>
                                <EW>
                                    <Name>Target</Name>
                                    <Choice>Manager</Choice>
                                    <Choice>DAQ</Choice>
                                    <Choice>Duts</Choice>
                                    <Choice>Robots</Choice>
                                    <Choice>Script</Choice>
                                    <Choice>Camera</Choice>
                                    <Val>0</Val>
                                </EW>
                                <String>
                                    <Name>Command</Name>
                                    <Val></Val>
                                </String>
                                <Array>
                                    <Name>Data</Name>
                                    <Dimsize>0</Dimsize>
                                    <String>
                                        <Name></Name>
                                        <Val></Val>
                                    </String>
                                </Array>
                                <String>
                                    <Name>ID</Name>
                                    <Val></Val>
                                </String>
                            </Cluster>
                            """  
        self._root = ElementTree.fromstring( clusterXml )

        self.Sender = self._getVal("Sender")
        self.Target = self._getVal("Target")
        self.Command = self._getVal("Command")
        self.Data = self._getVal("Data")
        self.ID = self._getVal("ID")

    def tostring( self ):
        self._setVal( "Sender", self.Sender )
        self._setVal( "Target", self.Target )
        self._setVal( "Command", self.Command )
        self._setVal( "Data", self.Data )
        self._setVal( "ID", self.ID )
        # fix the braindead way of LabVIEW not understanding about empty tags..
        return ElementTree.tostring( self._root ).replace("<Name />","<Name></Name>").replace("<Val />","<Val></Val>")


    # tries to find an element that contains a <Name>-tag with a matching name
    # return None, if no matching element was found
    def _findElement( self, name, node=None ):
        if node == None:
            node = self._root
            
        for element in list(node):
            if element.findtext("Name") == name:
                return element
        return None


    # retrieves the contents of <Val>-tag from within a node that contains a matching <Name>-tag
    def _getVal( self, name, node=None ):
        element = self._findElement( name, node )

        # if we did not find the name, return None
        if element == None:
            data = None

        # if the element is an array, populate and return a list        
        elif element.tag == "Array":
            data = []
            for subelement in list( element ):
                value = subelement.findtext("Val")
                if value != None:
                    data.append( value )

        # otherwise return the actual value, or None, if no value was present        
        else:        
            data = element.findtext("Val")

        return data
    
                
    # stores values into <Val>-tag with matching <Name>-tag
    def _setVal( self, name, value, node=None ):
        element = self._findElement( name, node )

        # raise KeyError, if the name was not found        
        if element == None:
            raise KeyError("Cluster item '%s' was not found in cluster" % name)

        # if the value is a list, store it into an array        
        if type( value ) == list:
            
            if element.tag != "Array":
                raise ValueError("Cluster item '%s' is not an array" % name)

            # delete all nodes, except Name, DimSize and the first array item
            excessNodes = list( element )[3:]
            for subelement in excessNodes:
                element.remove( subelement )

            # store array size
            element.find( "Dimsize" ).text = str( len( value ) )

            # store first array item value
            if len( value ) == 0:
                value = [ '' ]
            element.find( "String" ).find("Val").text = str( value[0] )

            # create and populate array item elements for the remaining items
            for item in value[1:]:
                newElement = ElementTree.Element("String")
                newElement.append( ElementTree.Element("Name") )
                newElement[-1].text = ''
                newElement.append( ElementTree.Element("Val") )
                newElement[-1].text = str( item )
                element.append( newElement )

        # otherwise store a scalar value                
        else:
            if element.tag == "Array":
                raise ValueError("Cluster item '%s' is an array" % name)
            element.find( "Val" ).text = str(value)
