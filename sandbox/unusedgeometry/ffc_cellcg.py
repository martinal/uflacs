
# FIXME: Consolidate ffc snippets with uflacs implementation. Use or copy? Nice to keep uflacs independent of ffc.
class FFCCellCodeGen:
    """
    Using names:
        vx(r) = vertex_coordinates(r)
        J(r)_## = jacobian entries
        detJ(r) = det(J)
        K(r)_## = inv(J)
        det = scale factor ???
        direction = boolean flip normal

        n(r)#
        volume(r)
        circumradius(r)
        facet_area

    """
    def __init__(self, celltype, gdim, tdim, restriction=''):
        self.gdim = gdim
        self.tdim = tdim
        self.vars = {
            'celltype': celltype,
            'gdim': gdim,
            'tdim': tdim,
            'restriction': restriction,
            }

    def jacobian(self):
        return ffc.codesnippets.jacobian[self.gdim] % self.vars

    def facet_determinant(self):
        return ffc.codesnippets.facet_determinant[self.gdim] % self.vars

    #def map_onto_physical(self):
    #    return ffc.codesnippets.map_onto_physical[self.gdim] % self.vars

    def normal_direction(self):
        return ffc.codesnippets.normal_direction[self.gdim] % self.vars

    def facet_normal(self):
        return ffc.codesnippets.facet_normal[self.gdim] % self.vars

    def cell_volume(self):
        return ffc.codesnippets.cell_volume[self.gdim] % self.vars

    def circumradius(self):
        return ffc.codesnippets.circumradius[self.gdim] % self.vars

    def facet_area(self):
        return ffc.codesnippets.facet_area[self.gdim] % self.vars