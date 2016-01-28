import warnings
from pysb import *
from pysb import ReactionPattern, ComplexPattern, ComponentDuplicateNameError


class Agent(object):
    def __init__(self, name, mods=None, mod_sites=None, active=None,
                 bound_to=None, bound_neg=None, db_refs=None):
        self.name = name
        if mods is None:
            self.mods = []
        else:
            self.mods = mods
        if mod_sites is None:
            self.mod_sites = []
        else:
            self.mod_sites = mod_sites
        self.bound_to = bound_to
        self.bound_neg = bound_neg
        self.active = active
        if db_refs is None:
            self.db_refs = {}
        else:
            self.db_refs = db_refs

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        attr_strs = []
        if self.mods:
            attr_strs.append('mods: %s' % self.mods)
        if self.mod_sites:
            attr_strs.append('mod_sites: %s' % self.mod_sites)
        if self.active:
            attr_strs.append('active: %s' % self.active)
        if self.bound_to:
            attr_strs.append('bound_to: %s' % self.bound_to)
        if self.bound_neg:
            attr_strs.append('bound_neg: %s' % self.bound_neg)
        if self.db_refs:
            attr_strs.append('db_refs: %s' % self.db_refs)
        attr_str = ', '.join(attr_strs)
        return '%s(%s)' % (self.name, attr_str)


class Statement(object):
    """The parent class of all statements"""
    def __init__(self, stmt=None, citation=None, evidence=None, 
                 annotations=None):
        self.stmt = stmt
        self.citation = citation
        self.evidence = evidence
        self.annotations = annotations

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if self.citation == other.citation and\
            self.evidence == other.evidence and\
            self.annotations == other.annotations and\
            self.stmt == other.stmt:
            return True
        else:
            return False


class Modification(Statement):
    """Generic statement representing the modification of a protein"""
    def __init__(self, enz, sub, mod, mod_pos, stmt=None,
                 citation=None, evidence=None, annotations=None):
        super(Modification, self).__init__(stmt, citation, evidence,
                                           annotations)
        self.enz = enz
        self.sub = sub
        self.mod = mod
        self.mod_pos = mod_pos

    def __str__(self):
        return ("%s(%s, %s, %s, %s)" %
                (type(self).__name__, self.enz.name, self.sub.name, self.mod,
                 self.mod_pos))

    def __eq__(self, other):
        if isinstance(other, Modification) and\
            self.enz == other.enz and\
            self.sub == other.sub and\
            self.mod == other.mod and\
            self.mod_pos == other.mod_pos:
            return True
        else:
            return False


class SelfModification(Statement):
    """Generic statement representing the self modification of a protein"""
    def __init__(self, enz, mod, mod_pos, stmt=None,
                 citation=None, evidence=None, annotations=None):
        super(SelfModification, self).__init__(stmt, citation, evidence,
                                           annotations)
        self.enz = enz
        self.mod = mod
        self.mod_pos = mod_pos

    def __str__(self):
        return ("%s(%s, %s, %s)" %
                (type(self).__name__, self.enz.name, self.mod, self.mod_pos))

    def __eq__(self, other):
        if isinstance(other, SelfModification) and\
            self.enz == other.enz and\
            self.mod == other.mod and\
            self.mod_pos == other.mod_pos:
            return True
        else:
            return False


class Phosphorylation(Modification):
    """Phosphorylation modification"""
    pass


class Autophosphorylation(SelfModification):
    """Autophosphorylation happens when a protein phosphorylates itself.

    A more precise name for this is cis-autophosphorylation.
    """
    pass


class Transphosphorylation(SelfModification):
    """Transphosphorylation assumes that a kinase is already bound to 
    a substrate (usually of the same molecular species), and phosphorylates 
    it in an intra-molecular fashion. The enz property of the statement must 
    have exactly one bound_to property, and we assume that enz phosphorylates 
    this bound_to molecule. The bound_neg property is ignored here.
    """
    pass


class Hydroxylation(Modification):
    """Hydroxylation modification"""
    pass


class Sumoylation(Modification):
    """Sumoylation modification"""
    pass


class Acetylation(Modification):
    """Acetylation modification"""
    pass


class Ubiquitination(Modification):
    """Ubiquitination modification"""
    pass


class ActivityActivity(Statement):
    """Statement representing the activation of a protein as a result of the
    activity of another protein."""
    def __init__(self, subj, subj_activity, relationship, obj,
                 obj_activity, stmt=None, citation=None, evidence=None,
                 annotations=None):
        super(ActivityActivity, self).__init__(stmt,
                                               citation, evidence, annotations)
        self.subj = subj
        self.subj_activity = subj_activity
        self.obj = obj
        self.obj_activity = obj_activity
        self.relationship = relationship

    def __eq__(self, other):
        if isinstance(other, ActivityActivity) and\
            self.subj == other.subj and\
            self.subj_activity == other.subj_activity and\
            self.obj == other.obj and\
            self.obj_activity == other.obj_activity:
            return True
        else:
            return False

    def __str__(self):
        return ("%s(%s, %s, %s, %s, %s)" %
                (type(self).__name__, self.subj.name, self.subj_activity,
                 self.relationship, self.obj.name, self.obj_activity))


class RasGtpActivityActivity(ActivityActivity):
    pass


class Dephosphorylation(Statement):
    def __init__(self, phos, sub, mod, mod_pos, stmt=None,
                 citation=None, evidence=None, annotations=None):
        super(Dephosphorylation, self).__init__(stmt, citation,
                                                evidence, annotations)
        self.phos = phos
        self.sub = sub
        self.mod = mod
        self.mod_pos = mod_pos

    def __eq__(self, other):
        if isinstance(other, Dephosphorylation) and\
            self.phos == other.phos and\
            self.sub == other.sub and\
            self.mod == other.mod and\
            self.mod_pos == other.mod_pos:
            return True
        else:
            return False

    def __str__(self):
        return ("Dephosphorylation(%s, %s, %s, %s)" %
                (self.phos.name, self.sub.name, self.mod, self.mod_pos))


class ActivityModification(Statement):
    """Statement representing the activation of a protein as a result
    of a residue modification"""
    def __init__(self, monomer, mod, mod_pos, relationship, activity,
                 stmt=None, citation=None, evidence=None, annotations=None):
        super(ActivityModification, self).__init__(stmt, citation,
                                                   evidence, annotations)
        self.monomer = monomer
        self.mod = mod
        self.mod_pos = mod_pos
        self.relationship = relationship
        self.activity = activity
    
    def __eq__(self, other):
        if isinstance(other, ActivityModification) and\
            self.monomer == other.monomer and\
            self.mod == other.mod and\
            self.mod_pos == other.mod_pos and\
            self.relationship == other.relationship and\
            self.activity == other.activity:
            return True
        else:
            return False

    def monomers_interactions_only(self, agent_set):
        pass

    def assemble_interactions_only(self, model, agent_set):
        pass

    def monomers_one_step(self, agent_set):
        agent = agent_set.get_create_base_agent(self.monomer)
        sites = site_name(self)
        active_states = [states[m][1] for m in self.mod]

        activity_pattern = {}
        for i, s in enumerate(sites):
            site_states = states[self.mod[i]]
            active_state = site_states[1]
            agent.create_site(s, site_states)
            activity_pattern[s] = active_state

        # Add this activity modification explicitly to the agent's list
        # of activating modifications
        agent.add_activating_modification(activity_pattern)
        # Inactivating modifications will require a different treatment
        # of the resolution of when the agent is active
        if self.relationship == 'decreases':
            warnings.warn('Inactivating modifications not currently '
                          'implemented!')

    def assemble_one_step(self, model, agent_set):
        pass

    def __str__(self):
        return ("ActivityModification(%s, %s, %s, %s, %s)" %
                (self.monomer.name, self.mod, self.mod_pos, self.relationship,
                 self.activity))

class ActivatingSubstitution(Statement):
    """Statement representing the activation of a protein as a result
    of a residue substitution"""
    def __init__(self, monomer, wt_residue, pos, sub_residue, activity, rel,
                 stmt=None, citation=None, evidence=None, annotations=None):
        super(ActivatingSubstitution, self).__init__(stmt, citation,
                                                     evidence, annotations)
        self.monomer = monomer
        self.wt_residue = wt_residue
        self.pos = pos
        self.sub_residue = sub_residue
        self.activity = activity
        self.rel = rel
    
    def __eq__(self, other):
        if isinstance(other, ActivatingSubstitution) and\
            self.monomer == other.monomer and\
            self.wt_residue == other.wt_residue and\
            self.pos == other.pos and\
            self.sub_residue == other.sub_residue and\
            self.activity == other.activity:
            return True
        else:
            return False

    def monomers_interactions_only(self, agent_set):
        pass

    def assemble_interactions_only(self, model, agent_set):
        pass

    def __str__(self):
        return ("ActivatingSubstitution(%s, %s, %s, %s, %s, %s)" %
                (self.monomer.name, self.wt_residue, self.pos,
                 self.sub_residue, self.activity, self.rel))

class RasGef(Statement):
    """Statement representing the activation of a GTP-bound protein
    upon Gef activity."""

    def __init__(self, gef, gef_activity, ras,
                 stmt=None, citation=None, evidence=None, annotations=None):
        super(RasGef, self).__init__(stmt, citation, evidence,
                                     annotations)
        self.gef = gef
        self.gef_activity = gef_activity
        self.ras = ras

    def __eq__(self, other):
        if isinstance(other, RasGef) and\
            self.gef == other.gef and\
            self.gef_activity == other.gef_activity and\
            self.ras == other.ras:
            return True
        else:
            return False

    def __str__(self):
        return ("RasGef(%s, %s, %s)" %
                (self.gef.name, self.gef_activity, self.ras.name))


class RasGap(Statement):
    """Statement representing the inactivation of a GTP-bound protein
    upon Gap activity."""
    def __init__(self, gap, gap_activity, ras,
                 stmt=None, citation=None, evidence=None, annotations=None):
        super(RasGap, self).__init__(stmt, citation, evidence,
                                     annotations)
        self.gap = gap
        self.gap_activity = gap_activity
        self.ras = ras

    def __eq__(self, other):
        if isinstance(other, RasGap) and\
            self.gap == other.gap and\
            self.gap_activity == other.gap_activity and\
            self.ras == other.ras:
            return True
        else:
            return False

    def monomers_interactions_only(self, agent_set):
        gap = agent_set.get_create_base_agent(self.gap)
        gap.create_site('gap_site')
        ras = agent_set.get_create_base_agent(self.ras)
        ras.create_site('gtp_site')

    def assemble_interactions_only(self, model, agent_set):
        kf_bind = get_create_parameter(model, 'kf_bind', 1.0, unique=False)
        gap = model.monomers[self.gap.name]
        ras = model.monomers[self.ras.name]
        r = Rule('%s_inactivates_%s' %
                 (self.gap.name, self.ras.name),
                 gap(**{'gap_site': None}) +
                 ras(**{'gtp_site': None}) >>
                 gap(**{'gap_site': 1}) +
                 ras(**{'gtp_site': 1}),
                 kf_bind)
        add_rule_to_model(model, r)

    def monomers_one_step(self, agent_set):
        gap = agent_set.get_create_base_agent(self.gap)
        gap.create_site(self.gap_activity, ('inactive', 'active'))
        ras = agent_set.get_create_base_agent(self.ras)
        ras.create_site('GtpBound', ('inactive', 'active'))

    def assemble_one_step(self, model, agent_set):
        gap_pattern = get_complex_pattern(model, self.gap, agent_set, 
            extra_fields={self.gap_activity: 'active'})
        ras_inactive = get_complex_pattern(model, self.ras, agent_set,
            extra_fields={'GtpBound': 'inactive'})
        ras_active = get_complex_pattern(model, self.ras, agent_set,
            extra_fields={'GtpBound': 'active'})

        param_name = 'kf_' + self.gap.name[0].lower() +\
                        self.ras.name[0].lower() + '_gap'
        kf_gap = get_create_parameter(model, param_name, 1e-6)

        r = Rule('%s_deactivates_%s' %
                 (self.gap.name, self.ras.name),
                 gap_pattern + ras_active >>
                 gap_pattern + ras_inactive,
                 kf_gap)
        add_rule_to_model(model, r)

    def __str__(self):
        return ("RasGap(%s, %s, %s)" %
                (self.gap.name, self.gap_activity, self.ras.name))


class Complex(Statement):
    """Statement representing complex formation between a set of members"""
    def __init__(self, members, stmt=None, citation=None, 
                 evidence=None, annotations=None):
        super(Complex, self).__init__(stmt, citation, evidence, annotations)
        self.members = members

    def __eq__(self, other):
        # TODO: find equality for different orders of members too
        if not isinstance(other, Complex):
            return False
        for (m1, m2) in zip(self.members, other.members):
            if not m1 == m2:
                return False
        return True

    def __str__(self):
        return ("Complex(%s)" % [m.name for m in self.members])
